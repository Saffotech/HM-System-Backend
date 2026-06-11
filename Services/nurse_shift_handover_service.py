from datetime import datetime, date
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from Models.department import Department
from Models.patient import Patient
from Models.user import User
from Models.opd_billing import Bed
from Models.nurse_shift_handover import (
    ShiftHandover,
    ShiftHandoverPatient,
    HandoverStatus)
from Schemas.nurse_shift_handover_schema import (
    ShiftHandoverCreate,
    ShiftHandoverUpdate,
    ShiftHandoverPatientUpdate,
    ShiftHandoverPatientsBulkCreate)

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

        handover_patient = (
            ShiftHandoverPatient(

                handover_id=handover.id,
                patient_id=patient.id,
                patient_name=patient_name,
                bed_number=bed.bed_number

                if bed else None,

                patient_summary=item.patient_summary,
                pending_tasks=item.pending_tasks,
                critical_alerts=item.critical_alerts,
                medication_pending=item.medication_pending,
                doctor_instructions=item.doctor_instructions,

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
# HANDOVER LIST
# ==========================================================

def get_handover_list_service(
    db: Session,

    handover_uid: str | None = None,

    patient_id: int | None = None,

    patient_name: str | None = None,

    status: str | None = None,

    ward_name: str | None = None,

    shift_date: date | None = None,

    outgoing_nurse_id: int | None = None,

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

    # ======================================================
    # TOTAL COUNT
    # ======================================================

    total_records = (
        query
        .count()
    )

    # ======================================================
    # PAGINATION
    # ======================================================

    records = (
        query
        .order_by(
            ShiftHandover.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    # ======================================================
    # RESPONSE
    # ======================================================

    data = []

    for handover in records:

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
    # OUTGOING NURSE
    # ======================================================

    nurse = (
        db.query(User)
        .filter(
            User.id ==
            handover.outgoing_nurse_id
        )
        .first()
    )

    nurse_name = None

    if nurse:

        nurse_name = (
            f"{nurse.first_name} "
            f"{nurse.last_name or ''}"
        ).strip()

    patients = (
        db.query(
            ShiftHandoverPatient
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
            nurse_name,

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

        "created_at":
            handover.created_at,

        "updated_at":
            handover.updated_at,

        "patients":
            patient_data
    }