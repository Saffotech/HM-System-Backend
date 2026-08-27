from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from Models.user import User
from Models.opd_billing import Appointment, Bed
from Models.patient import Patient
from Models.nurse_patient_vitals import PatientVitals, VitalStatus
from Services.ipd_helpers import attending_doctors_for_patients, doctor_name_map

from Schemas.nurse_schema import (
    VitalCreate,
    VitalUpdate,
    VitalResponse,
)

IST = ZoneInfo("Asia/Kolkata")


def _paginate_vitals(
    db: Session,
    query,
    *,
    page: int,
    page_size: int,
    latest_per_patient: bool,
):
    """
    Registry lists use latest_per_patient=True (one row per patient).
    Patient timeline / filtered history keep latest_per_patient=False (all rows).
    Detail payload includes full history across create recordings for the patient.

    Returns {"items", "total", "page", "page_size"} — routers may still emit the
    items array for existing clients and attach totals via response headers.
    """
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)

    if not latest_per_patient:
        total = query.order_by(None).count()
        vitals = (
            query.order_by(PatientVitals.recorded_at.desc(), PatientVitals.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        enriched = _enrich_vitals_batch(db, vitals)
        return {
            "items": [_serialize_vital(vital, db) for vital in enriched],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    latest_subq = (
        query.enable_eagerloads(False)
        .order_by(None)
        .with_entities(
            PatientVitals.patient_id.label("patient_id"),
            func.max(PatientVitals.id).label("max_id"),
        )
        .group_by(PatientVitals.patient_id)
        .subquery()
    )
    latest_query = _vital_query(db).join(
        latest_subq, PatientVitals.id == latest_subq.c.max_id
    )
    total = latest_query.order_by(None).count()
    vitals = (
        latest_query.order_by(PatientVitals.recorded_at.desc(), PatientVitals.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    enriched = _enrich_vitals_batch(db, vitals)
    return {
        "items": [_serialize_vital(vital, db) for vital in enriched],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name} {user.last_name or ''}".strip()


def _patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return f"{patient.first_name} {patient.last_name or ''}".strip()


def _appointment_doctor_id(vital: PatientVitals) -> int | None:
    appointment = getattr(vital, "appointment", None)
    if appointment and appointment.doctor_id:
        return appointment.doctor_id
    return None


def _attach_patient_doctor(
    db: Session,
    vital: PatientVitals,
    extra_doctor_id: int | None = None,
) -> None:
    doctor_id, doctor_name = attending_doctors_for_patients(
        db, [vital.patient_id]
    ).get(vital.patient_id, (None, None))
    if not doctor_id and extra_doctor_id:
        doctor_id = extra_doctor_id
        doctor_name = doctor_name_map(db, [extra_doctor_id]).get(extra_doctor_id)
    vital.doctor_id = doctor_id
    vital.doctor_name = doctor_name


def _enrich_vital(db: Session, vital: PatientVitals) -> PatientVitals:
    patient = (
        db.query(Patient)
        .filter(Patient.id == vital.patient_id)
        .first()
    )
    if patient:
        vital.patient_uid = patient.patient_uid
        vital.patient_name = _patient_display_name(patient)

    bed = (
        db.query(Bed)
        .filter(
            Bed.patient_id == vital.patient_id,
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .first()
    )
    if bed:
        vital.bed_number = bed.bed_number
        vital.ward_name = bed.ward_name

    _attach_patient_doctor(db, vital, extra_doctor_id=_appointment_doctor_id(vital))

    nurse = (
        db.query(User)
        .filter(User.id == vital.recorded_by)
        .first()
    )
    if nurse:
        vital.recorded_by_name = _user_display_name(nurse)

    return vital


def _enrich_vitals_batch(
    db: Session,
    vitals: list[PatientVitals],
) -> list[PatientVitals]:
    if not vitals:
        return vitals

    patient_ids = {v.patient_id for v in vitals}
    nurse_ids = {v.recorded_by for v in vitals}

    patients = {
        p.id: p
        for p in db.query(Patient)
        .filter(Patient.id.in_(patient_ids))
        .all()
    }
    nurses = {
        u.id: u
        for u in db.query(User)
        .filter(User.id.in_(nurse_ids))
        .all()
    }
    beds = {}
    for bed in (
        db.query(Bed)
        .filter(
            Bed.patient_id.in_(patient_ids),
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .all()
    ):
        if bed.patient_id not in beds:
            beds[bed.patient_id] = bed

    extra_doctor_ids: dict[int, int] = {}
    appointment_ids = {v.appointment_id for v in vitals if v.appointment_id}
    if appointment_ids:
        for appointment in (
            db.query(Appointment)
            .filter(Appointment.id.in_(appointment_ids))
            .all()
        ):
            extra_doctor_ids[appointment.id] = appointment.doctor_id

    attending_map = attending_doctors_for_patients(db, patient_ids)
    fallback_ids = [
        extra_doctor_ids.get(v.appointment_id)
        for v in vitals
        if v.appointment_id and not attending_map.get(v.patient_id, (None, None))[0]
    ]
    fallback_names = doctor_name_map(db, fallback_ids)

    for vital in vitals:
        patient = patients.get(vital.patient_id)
        if patient:
            vital.patient_uid = patient.patient_uid
            vital.patient_name = _patient_display_name(patient)

        bed = beds.get(vital.patient_id)
        if bed:
            vital.bed_number = bed.bed_number
            vital.ward_name = bed.ward_name

        doctor_id, doctor_name = attending_map.get(vital.patient_id, (None, None))
        if not doctor_id and vital.appointment_id:
            extra_id = extra_doctor_ids.get(vital.appointment_id)
            if extra_id:
                doctor_id = extra_id
                doctor_name = fallback_names.get(extra_id)
        vital.doctor_id = doctor_id
        vital.doctor_name = doctor_name

        nurse = nurses.get(vital.recorded_by)
        if nurse:
            vital.recorded_by_name = _user_display_name(nurse)

    return vitals


def _status_value(status) -> str | None:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def _history_entry(vital: PatientVitals) -> dict:
    return {
        "history_id": vital.id,
        "recorded_at": vital.recorded_at,
        "recorded_by": getattr(vital, "recorded_by_name", None),
        "status": _status_value(vital.status) or "recorded",
        "temperature": vital.temperature,
        "blood_pressure": vital.blood_pressure,
        "heart_rate": vital.heart_rate,
        "respiratory_rate": vital.respiratory_rate,
        "oxygen_saturation": vital.oxygen_saturation,
        "blood_sugar": vital.blood_sugar,
        "weight": vital.weight,
        "pain_level": vital.pain_level,
        "observation_notes": vital.observation_notes,
    }


def _patient_vital_history(db: Session, patient_id: int) -> list[dict]:
    """All recordings for a patient, newest first — powers Recorded At filter."""
    rows = (
        db.query(PatientVitals)
        .filter(PatientVitals.patient_id == patient_id)
        .order_by(PatientVitals.recorded_at.desc(), PatientVitals.id.desc())
        .all()
    )
    if not rows:
        return []

    nurse_ids = {v.recorded_by for v in rows if v.recorded_by}
    nurses = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(nurse_ids)).all()
    } if nurse_ids else {}

    history = []
    for row in rows:
        nurse = nurses.get(row.recorded_by)
        row.recorded_by_name = _user_display_name(nurse)
        history.append(_history_entry(row))
    return history


def _serialize_vital(vital: PatientVitals, db: Session | None = None) -> VitalResponse:
    patient = vital.patient
    nurse = getattr(vital, "nurse", None)
    recorded_by_name = (
        getattr(vital, "recorded_by_name", None)
        or _user_display_name(nurse)
    )
    history = _patient_vital_history(db, vital.patient_id) if db is not None else None
    payload = {
        "patient_uid": getattr(vital, "patient_uid", None)
        or (patient.patient_uid if patient else None),
        "patient_name": getattr(vital, "patient_name", None)
        or _patient_display_name(patient),
        "bed_number": getattr(vital, "bed_number", None),
        "ward_name": getattr(vital, "ward_name", None),
        "doctor_id": getattr(vital, "doctor_id", None),
        "doctor_name": getattr(vital, "doctor_name", None),
        "recorded_by_name": recorded_by_name,
        "nurse_name": recorded_by_name,
        "status": _status_value(vital.status),
    }
    if history is not None:
        payload["history"] = history
    return VitalResponse.model_validate(vital).model_copy(update=payload)


def _vital_query(db: Session):
    return db.query(PatientVitals).options(
        joinedload(PatientVitals.patient)
    )


def _occupied_bed_for_patient(db: Session, patient_id: int) -> Bed | None:
    return (
        db.query(Bed)
        .filter(
            Bed.patient_id == patient_id,
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .first()
    )


def _resolve_patient_and_appointment(
    db: Session,
    *,
    appointment_id: int | None,
    patient_id: int | None,
) -> tuple[Patient, Appointment | None]:
    """
    OPD: resolve via appointment_id.
    IPD: allow patient_id when the patient occupies a bed; optionally
    attach today's/latest non-cancelled appointment when one exists.
    """
    appointment: Appointment | None = None

    if appointment_id is not None:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if patient_id is not None and patient_id != appointment.patient_id:
            raise HTTPException(
                status_code=400,
                detail="patient_id does not match appointment",
            )
        patient = (
            db.query(Patient)
            .filter(Patient.id == appointment.patient_id)
            .first()
        )
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient, appointment

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active == True)  # noqa: E712
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not _occupied_bed_for_patient(db, patient.id):
        raise HTTPException(
            status_code=400,
            detail=(
                "patient_id is only allowed for patients currently occupying a bed, "
                "or provide appointment_id"
            ),
        )

    return patient, None


# ==========================================================
# CREATE VITAL
# ==========================================================

def create_vital_service(
    db: Session,
    vital_data: VitalCreate,
    nurse_id: int
):

    patient, appointment = _resolve_patient_and_appointment(
        db,
        appointment_id=vital_data.appointment_id,
        patient_id=vital_data.patient_id,
    )

    if appointment is not None:
        existing_vital = (
            db.query(PatientVitals)
            .filter(PatientVitals.appointment_id == appointment.id)
            .first()
        )
        if existing_vital:
            raise HTTPException(
                status_code=400,
                detail="Vitals already recorded for this appointment",
            )
    else:
        # IPD without appointment: block duplicate open vital for same patient today
        day_start = datetime.now(IST).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        existing_today = (
            db.query(PatientVitals)
            .filter(
                PatientVitals.patient_id == patient.id,
                PatientVitals.appointment_id.is_(None),
                PatientVitals.recorded_at >= day_start,
            )
            .first()
        )
        if existing_today:
            raise HTTPException(
                status_code=400,
                detail="Vitals already recorded today for this IPD patient",
            )

    try:

        vital = PatientVitals(
            appointment_id=appointment.id if appointment else None,
            patient_id=patient.id,
            recorded_by=nurse_id,

            status="recorded",

            temperature=vital_data.temperature,
            blood_pressure=vital_data.blood_pressure,
            heart_rate=vital_data.heart_rate,
            respiratory_rate=vital_data.respiratory_rate,
            oxygen_saturation=vital_data.oxygen_saturation,
            blood_sugar=vital_data.blood_sugar,
            weight=vital_data.weight,
            pain_level=vital_data.pain_level,
            observation_notes=vital_data.observation_notes
        )

        db.add(vital)

        db.commit()
        db.refresh(vital)
        vital = (
            _vital_query(db)
            .filter(PatientVitals.id == vital.id)
            .first()
        )

        return _serialize_vital(_enrich_vital(db, vital), db)

    except Exception:
        db.rollback()
        raise


# ==========================================================
# UPDATE VITAL
# ==========================================================

def update_vital_service(
    db: Session,
    vital_id: int,
    vital_data: VitalUpdate,
    nurse_id: int,
):
    """Append a new vitals snapshot (keeps prior rows for history filter)."""

    vital = (
        db.query(PatientVitals)
        .filter(
            PatientVitals.id == vital_id
        )
        .first()
    )

    if not vital:
        raise HTTPException(
            status_code=404,
            detail="Vital record not found"
        )

    try:

        update_data = (
            vital_data.model_dump(
                exclude_unset=True
            )
        )

        allowed_fields = (
            "temperature",
            "blood_pressure",
            "heart_rate",
            "respiratory_rate",
            "oxygen_saturation",
            "blood_sugar",
            "weight",
            "pain_level",
            "observation_notes",
        )

        snapshot_values = {
            field: getattr(vital, field)
            for field in allowed_fields
        }
        for field in allowed_fields:
            if field in update_data:
                snapshot_values[field] = update_data[field]

        now = datetime.now(IST)
        new_vital = PatientVitals(
            appointment_id=vital.appointment_id,
            patient_id=vital.patient_id,
            recorded_by=nurse_id,
            status=VitalStatus.RECORDED,
            temperature=snapshot_values["temperature"],
            blood_pressure=snapshot_values["blood_pressure"],
            heart_rate=snapshot_values["heart_rate"],
            respiratory_rate=snapshot_values["respiratory_rate"],
            oxygen_saturation=snapshot_values["oxygen_saturation"],
            blood_sugar=snapshot_values["blood_sugar"],
            weight=snapshot_values["weight"],
            pain_level=snapshot_values["pain_level"],
            observation_notes=snapshot_values["observation_notes"],
            created_by=nurse_id,
            updated_by=nurse_id,
            recorded_at=now,
            updated_at=now,
        )

        db.add(new_vital)
        db.commit()
        db.refresh(new_vital)
        new_vital = (
            _vital_query(db)
            .filter(PatientVitals.id == new_vital.id)
            .first()
        )

        return _serialize_vital(_enrich_vital(db, new_vital), db)

    except Exception:
        db.rollback()
        raise


# ==========================================================
# GET SINGLE VITAL
# ==========================================================

def get_vital_by_id_service(
    db: Session,
    vital_id: int
):

    vital = (
        _vital_query(db)
        .filter(
            PatientVitals.id == vital_id
        )
        .first()
    )

    if not vital:
        raise HTTPException(
            status_code=404,
            detail="Vital record not found"
        )

    return _serialize_vital(_enrich_vital(db, vital), db)


# ==========================================================
# GET ALL VITALS
# ==========================================================

def get_all_vitals_service(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    allocated_only: bool = False,
    nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,
):

    query = _vital_query(db)

    if allocated_only:
        from Services.nurse_shift_bed_allocation_service import (
            get_allocated_patient_ids_for_nurse,
        )

        patient_ids = get_allocated_patient_ids_for_nurse(
            db,
            nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        ) if nurse_id else []
        if not patient_ids:
            query = query.filter(PatientVitals.patient_id == -1)
        else:
            query = query.filter(PatientVitals.patient_id.in_(patient_ids))

    return _paginate_vitals(
        db,
        query,
        page=page,
        page_size=page_size,
        latest_per_patient=True,
    )


# ==========================================================
# SEARCH / FILTER VITALS
# ==========================================================

def search_vitals_service(
    db: Session,

    patient_id: int | None = None,
    patient_uid: str | None = None,
    appointment_id: int | None = None,

    name: str | None = None,
    phone: str | None = None,

    status: str | None = None,
    recorded_by: int | None = None,

    from_date: date | None = None,
    to_date: date | None = None,

    allocated_only: bool = False,
    nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = _vital_query(db)

    if patient_id:
        query = query.filter(
            PatientVitals.patient_id == patient_id
        )

    if appointment_id:
        query = query.filter(
            PatientVitals.appointment_id == appointment_id
        )

    if name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{name}%"
                ),
                Patient.last_name.ilike(
                    f"%{name}%"
                )
            )
        )

    if phone:
        query = query.filter(
            Patient.phone.ilike(
                f"%{phone}%"
            )
        )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if status:
        query = query.filter(
            PatientVitals.status == status
        )

    if recorded_by:
        query = query.filter(
            PatientVitals.recorded_by == recorded_by
        )

    if from_date:
        query = query.filter(
            PatientVitals.recorded_at >= from_date
        )

    if to_date:
        query = query.filter(
            PatientVitals.recorded_at <
            (to_date + timedelta(days=1))
        )

    if allocated_only:
        from Services.nurse_shift_bed_allocation_service import (
            get_allocated_patient_ids_for_nurse,
        )

        patient_ids = get_allocated_patient_ids_for_nurse(
            db,
            nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        ) if nurse_id else []
        if not patient_ids:
            query = query.filter(PatientVitals.patient_id == -1)
        else:
            query = query.filter(PatientVitals.patient_id.in_(patient_ids))

    # Patient/appointment history views need every snapshot; registry wants one row each.
    latest_per_patient = patient_id is None and appointment_id is None
    return _paginate_vitals(
        db,
        query,
        page=page,
        page_size=page_size,
        latest_per_patient=latest_per_patient,
    )