from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload, aliased

from Constants.constants import Role as RoleEnum
from Models.department import Department
from Models.doctor_prescriptions import (
    Prescription,
    PrescriptionItem,
)
from Models.nurse_medication_administration import (
    MedicationAdministration,
    MedicationStatus,
)
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_handover import (
    ShiftHandover,
    ShiftHandoverPatient,
    HandoverStatus,
)
from Models.opd_billing import Bed
from Models.patient import Patient
from Models.user import User
from Schemas.nurse_shift_handover_schema import (
    ShiftHandoverCreate,
    ShiftHandoverUpdate,
    ShiftHandoverPatientUpdate,
    ShiftHandoverPatientsBulkCreate,
    ShiftHandoverTakeOver,
)
from Services.nurse_emergency_alert_triggers import (
    get_active_alerts_text_for_patient,
)
from Services.notification_service import notify_nurse_handover_taken_over

# ==========================================================
# HELPERS
# ==========================================================

def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


def _generate_handover_uid(db: Session):
    current_year = datetime.now().year
    last_record = (db.query(ShiftHandover)
        .order_by(ShiftHandover.id.desc())
        .first())
    next_number = 1
    if last_record:
        next_number = (last_record.id + 1)

    return (
        f"HO-{current_year}-"
        f"{str(next_number).zfill(6)}"
    )


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name} {user.last_name or ''}".strip()


def _is_nurse_user(user: User | None) -> bool:
    if not user or not user.role_obj:
        return False
    return user.role_obj.name == RoleEnum.NURSE


def _format_vitals_summary(vital: PatientVitals) -> str:
    parts = []
    if vital.temperature is not None:
        parts.append(f"Temp {vital.temperature}")
    if vital.blood_pressure:
        parts.append(f"BP {vital.blood_pressure}")
    if vital.heart_rate is not None:
        parts.append(f"HR {vital.heart_rate}")
    if vital.respiratory_rate is not None:
        parts.append(f"RR {vital.respiratory_rate}")
    if vital.oxygen_saturation is not None:
        parts.append(f"SpO2 {vital.oxygen_saturation}")
    if vital.blood_sugar is not None:
        parts.append(f"BS {vital.blood_sugar}")
    if vital.pain_level is not None:
        parts.append(f"Pain {vital.pain_level}/10")
    if vital.observation_notes:
        parts.append(vital.observation_notes.strip())

    recorded = (
        vital.recorded_at.strftime("%Y-%m-%d %H:%M")
        if vital.recorded_at
        else "unknown time"
    )
    if not parts:
        return f"Last vitals recorded at {recorded}"
    return f"Last vitals ({recorded}): " + ", ".join(parts)


def _build_patient_care_snapshot(
    db: Session,
    patient_id: int,
    shift_date: date | None = None,
) -> dict:
    """Auto-fill handover patient fields from clinical work already done."""

    day = shift_date or _now().date()
    day_start = datetime(
        day.year,
        day.month,
        day.day,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    day_end = day_start + timedelta(days=1)

    latest_vital = (
        db.query(PatientVitals)
        .filter(PatientVitals.patient_id == patient_id)
        .order_by(PatientVitals.recorded_at.desc())
        .first()
    )

    latest_note = (
        db.query(NursingNote)
        .filter(NursingNote.patient_id == patient_id)
        .order_by(NursingNote.created_at.desc())
        .first()
    )

    summary_parts: list[str] = []
    if latest_vital:
        summary_parts.append(_format_vitals_summary(latest_vital))
    if latest_note:
        note_bits = [
            bit.strip()
            for bit in [
                latest_note.symptoms,
                latest_note.treatment_response,
                latest_note.additional_notes,
            ]
            if bit and bit.strip()
        ]
        if note_bits:
            summary_parts.append("Nursing note: " + "; ".join(note_bits))

    administrations = (
        db.query(MedicationAdministration)
        .filter(
            MedicationAdministration.patient_id == patient_id,
            MedicationAdministration.administered_at >= day_start,
            MedicationAdministration.administered_at < day_end,
        )
        .order_by(MedicationAdministration.administered_at.desc())
        .all()
    )

    given_parts = []
    issue_parts = []
    given_item_ids: set[int] = set()

    for admin in administrations:
        label = admin.medicine_name
        if admin.dosage:
            label = f"{label} {admin.dosage}"
        if admin.status == MedicationStatus.GIVEN:
            given_parts.append(label)
            given_item_ids.add(admin.prescription_item_id)
        elif admin.status in (
            MedicationStatus.MISSED,
            MedicationStatus.DELAYED,
            MedicationStatus.REFUSED,
        ):
            issue_parts.append(
                f"{label} ({admin.status.value})"
            )

    if given_parts:
        # Keep unique while preserving order
        unique_given = list(dict.fromkeys(given_parts))
        summary_parts.append(
            "Meds given this shift: " + ", ".join(unique_given)
        )

    prescription = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .first()
    )

    pending_parts = list(dict.fromkeys(issue_parts))
    instruction_parts: list[str] = []

    if prescription:
        if prescription.notes and prescription.notes.strip():
            instruction_parts.append(prescription.notes.strip())
        if prescription.diagnosis and prescription.diagnosis.strip():
            instruction_parts.append(
                f"Diagnosis: {prescription.diagnosis.strip()}"
            )

        items = (
            db.query(PrescriptionItem)
            .filter(PrescriptionItem.prescription_id == prescription.id)
            .all()
        )

        ever_given_ids = {
            row[0]
            for row in (
                db.query(MedicationAdministration.prescription_item_id)
                .filter(
                    MedicationAdministration.patient_id == patient_id,
                    MedicationAdministration.status == MedicationStatus.GIVEN,
                    MedicationAdministration.prescription_item_id.in_(
                        [item.id for item in items] or [-1]
                    ),
                )
                .distinct()
                .all()
            )
        }

        for item in items:
            if item.instructions and item.instructions.strip():
                instruction_parts.append(
                    f"{item.medicine_name}: {item.instructions.strip()}"
                )
            if item.id not in ever_given_ids and item.id not in given_item_ids:
                pending_label = item.medicine_name
                if item.dosage:
                    pending_label = f"{pending_label} {item.dosage}"
                if item.frequency:
                    pending_label = f"{pending_label} ({item.frequency})"
                pending_parts.append(pending_label)

    critical_alerts = get_active_alerts_text_for_patient(db, patient_id)

    task_parts: list[str] = []
    if pending_parts:
        task_parts.append(
            f"{len(list(dict.fromkeys(pending_parts)))} medication(s) pending/attention"
        )
    if critical_alerts:
        task_parts.append("Review active critical alerts")
    if not latest_vital or (
        latest_vital.recorded_at and latest_vital.recorded_at < day_start
    ):
        task_parts.append("Vitals due / outdated")

    return {
        "patient_summary": " | ".join(summary_parts) if summary_parts else None,
        "medication_pending": (
            "; ".join(dict.fromkeys(pending_parts)) if pending_parts else None
        ),
        "doctor_instructions": (
            "; ".join(dict.fromkeys(instruction_parts))
            if instruction_parts
            else None
        ),
        "critical_alerts": critical_alerts,
        "pending_tasks": "; ".join(task_parts) if task_parts else None,
    }

# ==========================================================
# CREATE HANDOVER
# ==========================================================

def create_handover_service(
    db: Session,
    handover_data: ShiftHandoverCreate,
    nurse_id: int
):

    if handover_data.department_id:

        department = (db.query(Department)
            .filter(Department.id ==handover_data.department_id)
            .first()
        )

        if not department:
            raise HTTPException(
                status_code=404,
                detail="Department not found"
            )

    handover_uid = (_generate_handover_uid(db))

    handover = ShiftHandover(

        handover_uid=handover_uid,
        outgoing_nurse_id=nurse_id,
        department_id=handover_data.department_id,
        ward_name=handover_data.ward_name,
        shift_date=handover_data.shift_date or _now().date(),
        shift_start=handover_data.shift_start,
        shift_end=handover_data.shift_end,
        general_notes=handover_data.general_notes,
        status=HandoverStatus.PENDING,
        created_by=nurse_id,
        updated_by=nurse_id
    )

    try:

        db.add(handover)
        db.commit()
        db.refresh(handover)


    except Exception as e:

        db.rollback()
        print("HANDOVER ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    return handover

# ==========================================================
# BULK ADD HANDOVER PATIENTS
# ==========================================================

def bulk_add_handover_patients_service(
    db: Session,
    handover_id: int,
    patient_data: ShiftHandoverPatientsBulkCreate,
    nurse_id: int
):

    handover = (db.query(ShiftHandover)
        .filter(ShiftHandover.id == handover_id)
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    # ======================================================
    # ONLY CREATOR CAN MODIFY
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own handover"
        )

    # ======================================================
    # SUBMITTED HANDOVER LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    records_to_insert = []

    # ======================================================
    # PROCESS PATIENTS
    # ======================================================

    for item in patient_data.patients:

        patient = (db.query(Patient)
            .filter(Patient.id == item.patient_id,
                Patient.is_active == True
            ).first()
        )

        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient {item.patient_id} not found"
            )

        # ==================================================
        # DUPLICATE CHECK
        # ==================================================

        existing = (db.query(ShiftHandoverPatient)
            .filter(ShiftHandoverPatient.handover_id== handover_id,
                        ShiftHandoverPatient.patient_id== item.patient_id
            ).first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Patient "
                    f"{item.patient_id} "
                    f"already exists "
                    f"in handover"
                )
            )

        # ==================================================
        # BED SNAPSHOT
        # ==================================================

        bed = (db.query(Bed)
            .filter(Bed.patient_id == patient.id,
                Bed.status == "occupied"
            ).order_by(Bed.admitted_at.desc())
            .first()
        )

        patient_name = (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip()

        snapshot = _build_patient_care_snapshot(
            db,
            patient.id,
            shift_date=handover.shift_date,
        )

        handover_patient = (
            ShiftHandoverPatient(

                handover_id=handover.id,
                patient_id=patient.id,
                patient_name=patient_name,
                bed_number=bed.bed_number

                if bed else None,

                patient_summary=(
                    item.patient_summary
                    if item.patient_summary is not None
                    else snapshot["patient_summary"]
                ),
                pending_tasks=(
                    item.pending_tasks
                    if item.pending_tasks is not None
                    else snapshot["pending_tasks"]
                ),
                critical_alerts=(
                    item.critical_alerts
                    if item.critical_alerts is not None
                    else snapshot["critical_alerts"]
                ),
                medication_pending=(
                    item.medication_pending
                    if item.medication_pending is not None
                    else snapshot["medication_pending"]
                ),
                doctor_instructions=(
                    item.doctor_instructions
                    if item.doctor_instructions is not None
                    else snapshot["doctor_instructions"]
                ),

                created_by=nurse_id,
                updated_by=nurse_id
            )
        )

        records_to_insert.append(
            handover_patient
        )
    try:
        db.add_all(records_to_insert)
        db.commit()

    except Exception:

        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=
            "Failed to add patients to handover"
        )

    return {
        "message":"Patients added successfully",
        "count":len(records_to_insert)
    }

# ==========================================================
# UPDATE HANDOVER
# ==========================================================

def update_handover_service(
    db: Session,
    handover_id: int,
    handover_data: ShiftHandoverUpdate,
    nurse_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (db.query(ShiftHandover)
        .filter(ShiftHandover.id == handover_id)
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own handover"
        )

    # ======================================================
    # SUBMITTED LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    # ======================================================
    # DEPARTMENT VALIDATION
    # ======================================================

    if handover_data.department_id:

        department = (
            db.query(Department)
            .filter(
                Department.id ==
                handover_data.department_id
            )
            .first()
        )

        if not department:
            raise HTTPException(
                status_code=404,
                detail="Department not found"
            )

    # ======================================================
    # UPDATE DATA
    # ======================================================

    update_data = (
        handover_data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in update_data.items():
        setattr(
            handover,
            field,
            value
        )

    handover.updated_by = nurse_id

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover)

        db.commit()

        db.refresh(handover)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update handover"
        )

    return handover

# ==========================================================
# UPDATE HANDOVER PATIENT
# ==========================================================

def update_handover_patient_service(
    db: Session,
    patient_summary_id: int,
    patient_data: ShiftHandoverPatientUpdate,
    nurse_id: int
):

    # ======================================================
    # PATIENT HANDOVER EXISTS
    # ======================================================

    handover_patient = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.id
            == patient_summary_id
        )
        .first()
    )

    if not handover_patient:
        raise HTTPException(
            status_code=404,
            detail="Patient handover record not found"
        )

    # ======================================================
    # PARENT HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .filter(
            ShiftHandover.id
            == handover_patient.handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Parent handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own handover"
        )

    # ======================================================
    # SUBMITTED LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    # ======================================================
    # UPDATE DATA
    # ======================================================

    update_data = (
        patient_data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in update_data.items():
        setattr(
            handover_patient,
            field,
            value
        )

    handover_patient.updated_by = nurse_id

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover_patient)

        db.commit()

        db.refresh(handover_patient)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update patient handover"
        )

    return handover_patient

# ==========================================================
# DELETE HANDOVER PATIENT
# ==========================================================

def delete_handover_patient_service(
    db: Session,
    patient_summary_id: int,
    nurse_id: int
):

    # ======================================================
    # PATIENT HANDOVER EXISTS
    # ======================================================

    handover_patient = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.id
            == patient_summary_id
        )
        .first()
    )

    if not handover_patient:
        raise HTTPException(
            status_code=404,
            detail="Patient handover record not found"
        )

    # ======================================================
    # PARENT HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .filter(
            ShiftHandover.id
            == handover_patient.handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Parent handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own handover"
        )

    # ======================================================
    # SUBMITTED LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    # ======================================================
    # DELETE
    # ======================================================

    try:

        db.delete(handover_patient)

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to delete patient handover"
        )

    return {
        "message":
            "Patient removed from handover successfully"
    }


# ==========================================================
# SUBMIT HANDOVER
# ==========================================================

def submit_handover_service(
    db: Session,
    handover_id: int,
    nurse_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .filter(
            ShiftHandover.id == handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only submit your own handover"
        )

    # ======================================================
    # ALREADY SUBMITTED
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Handover already submitted"
        )

    # ======================================================
    # PATIENT VALIDATION
    # ======================================================

    patient_count = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.handover_id
            == handover.id
        )
        .count()
    )

    if patient_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot submit handover "
                "without patient summaries"
            )
        )

    # Fill any blank care fields from live clinical data before locking
    patients = (
        db.query(ShiftHandoverPatient)
        .filter(ShiftHandoverPatient.handover_id == handover.id)
        .all()
    )
    for patient_row in patients:
        snapshot = _build_patient_care_snapshot(
            db,
            patient_row.patient_id,
            shift_date=handover.shift_date,
        )
        if not patient_row.patient_summary:
            patient_row.patient_summary = snapshot["patient_summary"]
        if not patient_row.pending_tasks:
            patient_row.pending_tasks = snapshot["pending_tasks"]
        if not patient_row.critical_alerts:
            patient_row.critical_alerts = snapshot["critical_alerts"]
        if not patient_row.medication_pending:
            patient_row.medication_pending = snapshot["medication_pending"]
        if not patient_row.doctor_instructions:
            patient_row.doctor_instructions = snapshot["doctor_instructions"]
        patient_row.updated_by = nurse_id

    # ======================================================
    # SUBMIT
    # ======================================================

    handover.status = (
        HandoverStatus.SUBMITTED
    )

    handover.submitted_at = (
        _now()
    )

    handover.updated_by = (
        nurse_id
    )

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover)

        db.commit()

        db.refresh(handover)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to submit handover"
        )

    return {
        "message":
            "Handover submitted successfully",

        "handover_id":
            handover.id,

        "handover_uid":
            handover.handover_uid,

        "status":
            handover.status
    }


# ==========================================================
# TAKE OVER HANDOVER (incoming nurse claims submitted form)
# ==========================================================

def take_over_handover_service(
    db: Session,
    handover_id: int,
    nurse_id: int,
    take_over_data: ShiftHandoverTakeOver | None = None,
):

    handover = (
        db.query(ShiftHandover)
        .filter(ShiftHandover.id == handover_id)
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found",
        )

    if handover.status != HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Only submitted handovers can be taken over",
        )

    if handover.outgoing_nurse_id == nurse_id:
        raise HTTPException(
            status_code=400,
            detail="Outgoing nurse cannot take over their own handover",
        )

    if handover.replacement_nurse_id is not None:
        current = (
            db.query(User)
            .filter(User.id == handover.replacement_nurse_id)
            .first()
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Handover already taken over by "
                f"{_user_display_name(current) or handover.replacement_nurse_id}"
            ),
        )

    nurse = (
        db.query(User)
        .options(joinedload(User.role_obj))
        .filter(User.id == nurse_id, User.is_active == True)
        .first()
    )

    if not _is_nurse_user(nurse):
        raise HTTPException(
            status_code=403,
            detail="Only a nurse can take over a handover",
        )

    notes = None
    if take_over_data:
        notes = take_over_data.take_over_notes

    handover.replacement_nurse_id = nurse_id
    handover.taken_over_at = _now()
    handover.take_over_notes = notes
    handover.updated_by = nurse_id

    try:
        db.add(handover)
        db.commit()
        db.refresh(handover)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to take over handover",
        )

    outgoing = (
        db.query(User)
        .filter(User.id == handover.outgoing_nurse_id)
        .first()
    )

    notify_nurse_handover_taken_over(
        db,
        outgoing_nurse_id=handover.outgoing_nurse_id,
        title="Handover taken over",
        message=(
            f"{_user_display_name(nurse) or 'A nurse'} took over your handover "
            f"{handover.handover_uid}."
            + (
                f"\nNotes: {notes}"
                if notes
                else ""
            )
        ),
        handover_id=handover.id,
        created_by=nurse_id,
        created_by_name=_user_display_name(nurse),
    )

    return {
        "message": "Handover taken over successfully",
        "handover_id": handover.id,
        "handover_uid": handover.handover_uid,
        "status": handover.status,
        "outgoing_nurse_id": handover.outgoing_nurse_id,
        "outgoing_nurse": _user_display_name(outgoing),
        "replacement_nurse_id": handover.replacement_nurse_id,
        "replacement_nurse": _user_display_name(nurse),
        "taken_over_at": handover.taken_over_at,
        "take_over_notes": handover.take_over_notes,
    }


# ==========================================================
# HANDOVER LIST
# ==========================================================

def get_handover_list_service(
    db: Session,

    handover_uid: str | None = None,

    patient_id: int | None = None,
    patient_uid: str | None = None,

    patient_name: str | None = None,

    status: str | None = None,

    ward_name: str | None = None,

    shift_date: date | None = None,

    outgoing_nurse_id: int | None = None,
    outgoing_nurse_name: str | None = None,

    replacement_nurse_id: int | None = None,
    taken_over: bool | None = None,

    page: int = 1,
    page_size: int = 20
):

    # ======================================================
    # PAGINATION VALIDATION
    # ======================================================

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100"
        )

    OutgoingNurse = aliased(User)
    ReplacementNurse = aliased(User)

    # ======================================================
    # BASE QUERY
    # ======================================================

    query = (
        db.query(ShiftHandover)
        .outerjoin(
            ShiftHandoverPatient,
            ShiftHandoverPatient.handover_id
            == ShiftHandover.id
        )
        .outerjoin(
            Patient,
            Patient.id
            == ShiftHandoverPatient.patient_id
        )
        .outerjoin(
            OutgoingNurse,
            OutgoingNurse.id == ShiftHandover.outgoing_nurse_id,
        )
        .outerjoin(
            ReplacementNurse,
            ReplacementNurse.id == ShiftHandover.replacement_nurse_id,
        )
    )

    # ======================================================
    # FILTERS
    # ======================================================

    if handover_uid:
        query = query.filter(
            ShiftHandover.handover_uid.ilike(
                f"%{handover_uid}%"
            )
        )

    if patient_id:
        query = query.filter(
            ShiftHandoverPatient.patient_id
            == patient_id
        )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if patient_name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{patient_name}%"
                ),
                Patient.last_name.ilike(
                    f"%{patient_name}%"
                )
            )
        )

    if status:
        query = query.filter(
            ShiftHandover.status == status
        )

    if ward_name:
        query = query.filter(
            ShiftHandover.ward_name.ilike(
                f"%{ward_name}%"
            )
        )

    if shift_date:
        query = query.filter(
            ShiftHandover.shift_date
            == shift_date
        )

    if outgoing_nurse_id:
        query = query.filter(
            ShiftHandover.outgoing_nurse_id
            == outgoing_nurse_id
        )

    if outgoing_nurse_name:
        like = f"%{outgoing_nurse_name}%"
        query = query.filter(
            or_(
                OutgoingNurse.first_name.ilike(like),
                OutgoingNurse.last_name.ilike(like),
                func.concat(
                    OutgoingNurse.first_name,
                    " ",
                    func.coalesce(OutgoingNurse.last_name, ""),
                ).ilike(like),
            )
        )

    if replacement_nurse_id:
        query = query.filter(
            ShiftHandover.replacement_nurse_id
            == replacement_nurse_id
        )

    if taken_over is True:
        query = query.filter(
            ShiftHandover.replacement_nurse_id.isnot(None)
        )
    elif taken_over is False:
        query = query.filter(
            ShiftHandover.replacement_nurse_id.is_(None)
        )

    # ======================================================
    # TOTAL COUNT (distinct handovers)
    # ======================================================

    total_records = (
        query.with_entities(ShiftHandover.id)
        .distinct()
        .count()
    )

    # ======================================================
    # PAGINATION
    # ======================================================

    handover_ids = [
        row[0]
        for row in (
            query.with_entities(
                ShiftHandover.id,
                ShiftHandover.created_at,
            )
            .distinct()
            .order_by(ShiftHandover.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    ]

    if not handover_ids:
        return {
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "data": [],
        }

    records = (
        db.query(ShiftHandover)
        .options(
            joinedload(ShiftHandover.outgoing_nurse),
            joinedload(ShiftHandover.replacement_nurse),
        )
        .filter(ShiftHandover.id.in_(handover_ids))
        .all()
    )

    record_map = {h.id: h for h in records}
    ordered = [record_map[hid] for hid in handover_ids if hid in record_map]

    # ======================================================
    # RESPONSE
    # ======================================================

    data = []

    for handover in ordered:

        patient_count = (
            db.query(
                ShiftHandoverPatient
            )
            .filter(
                ShiftHandoverPatient.handover_id
                == handover.id
            )
            .count()
        )

        data.append({

            "handover_id":
                handover.id,

            "handover_uid":
                handover.handover_uid,

            "outgoing_nurse_id":
                handover.outgoing_nurse_id,

            "outgoing_nurse":
                _user_display_name(handover.outgoing_nurse),

            "replacement_nurse_id":
                handover.replacement_nurse_id,

            "replacement_nurse":
                _user_display_name(handover.replacement_nurse),

            "ward_name":
                handover.ward_name,

            "shift_date":
                handover.shift_date,

            "status":
                handover.status,

            "patient_count":
                patient_count,

            "submitted_at":
                handover.submitted_at,

            "taken_over_at":
                handover.taken_over_at,

            "created_at":
                handover.created_at
        })

    return {

        "total_records":
            total_records,

        "page":
            page,

        "page_size":
            page_size,

        "data":
            data
    }


# ==========================================================
# HANDOVER DETAIL
# ==========================================================

def get_handover_detail_service(
    db: Session,
    handover_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .options(
            joinedload(ShiftHandover.outgoing_nurse),
            joinedload(ShiftHandover.replacement_nurse),
        )
        .filter(
            ShiftHandover.id == handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    patients = (
        db.query(
            ShiftHandoverPatient
        )
        .options(
            joinedload(ShiftHandoverPatient.patient)
        )
        .filter(
            ShiftHandoverPatient.handover_id
            == handover.id
        )
        .order_by(
            ShiftHandoverPatient.created_at.asc()
        )
        .all()
    )

    patient_data = []

    for patient in patients:

        patient_data.append({

            "id":
                patient.id,

            "patient_id":
                patient.patient_id,

            "patient_uid":
                patient.patient.patient_uid
                if patient.patient else None,

            "patient_name":
                patient.patient_name,

            "bed_number":
                patient.bed_number,

            "patient_summary":
                patient.patient_summary,

            "pending_tasks":
                patient.pending_tasks,

            "critical_alerts":
                patient.critical_alerts,

            "medication_pending":
                patient.medication_pending,

            "doctor_instructions":
                patient.doctor_instructions,

            "created_at":
                patient.created_at
        })

    return {

        "handover_id":
            handover.id,

        "handover_uid":
            handover.handover_uid,

        "outgoing_nurse_id":
            handover.outgoing_nurse_id,

        "outgoing_nurse":
            _user_display_name(handover.outgoing_nurse),

        "replacement_nurse_id":
            handover.replacement_nurse_id,

        "replacement_nurse":
            _user_display_name(handover.replacement_nurse),

        "department_id":
            handover.department_id,

        "ward_name":
            handover.ward_name,

        "shift_date":
            handover.shift_date,

        "shift_start":
            handover.shift_start,

        "shift_end":
            handover.shift_end,

        "general_notes":
            handover.general_notes,

        "status":
            handover.status,

        "submitted_at":
            handover.submitted_at,

        "taken_over_at":
            handover.taken_over_at,

        "take_over_notes":
            handover.take_over_notes,

        "created_at":
            handover.created_at,

        "updated_at":
            handover.updated_at,

        "patients":
            patient_data
    }