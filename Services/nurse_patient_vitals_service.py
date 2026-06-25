from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, Bed
from Models.patient import Patient
from Models.nurse_patient_vitals import PatientVitals
from Models.doctor_patient_queue import PatientQueue

from Schemas.nurse_schema import (
    VitalCreate,
    VitalUpdate
)

IST = ZoneInfo("Asia/Kolkata")


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name} {user.last_name or ''}".strip()


def _patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return f"{patient.first_name} {patient.last_name or ''}".strip()


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

    for vital in vitals:
        patient = patients.get(vital.patient_id)
        if patient:
            vital.patient_uid = patient.patient_uid
            vital.patient_name = _patient_display_name(patient)

        bed = beds.get(vital.patient_id)
        if bed:
            vital.bed_number = bed.bed_number

        nurse = nurses.get(vital.recorded_by)
        if nurse:
            vital.recorded_by_name = _user_display_name(nurse)

    return vitals


# ==========================================================
# CREATE VITAL
# ==========================================================

def create_vital_service(
    db: Session,
    vital_data: VitalCreate,
    nurse_id: int
):

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == vital_data.appointment_id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # Prevent duplicate vitals for same appointment
    existing_vital = (
        db.query(PatientVitals)
        .filter(
            PatientVitals.appointment_id == appointment.id
        )
        .first()
    )

    if existing_vital:
        raise HTTPException(
            status_code=400,
            detail="Vitals already recorded for this appointment"
        )

    try:

        vital = PatientVitals(
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
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

        queue = (
            db.query(PatientQueue)
            .filter(
                PatientQueue.appointment_id == appointment.id
            )
            .first()
        )

        if queue and queue.status == "waiting":
            queue.status = "vitals_completed"

        db.commit()
        db.refresh(vital)

        return vital

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

    if vital.recorded_by != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update vitals you recorded",
        )

    try:

        update_data = (
            vital_data.model_dump(
                exclude_unset=True
            )
        )

        for field, value in update_data.items():
            setattr(vital, field, value)

        vital.updated_at = datetime.now(IST)

        db.commit()
        db.refresh(vital)

        return vital

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

    return vital


# ==========================================================
# GET ALL VITALS
# ==========================================================

def get_all_vitals_service(
    db: Session,
    page: int = 1,
    page_size: int = 20
):

    return (
        db.query(PatientVitals)
        .order_by(
            PatientVitals.recorded_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )


# ==========================================================
# SEARCH / FILTER VITALS
# ==========================================================

def search_vitals_service(
    db: Session,

    patient_id: int | None = None,
    appointment_id: int | None = None,

    name: str | None = None,
    phone: str | None = None,
    uhid: str | None = None,

    status: str | None = None,
    recorded_by: int | None = None,

    from_date: date | None = None,
    to_date: date | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = (
        db.query(PatientVitals)
        .join(
            Patient,
            Patient.id == PatientVitals.patient_id
        )
    )

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

    if uhid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{uhid}%"
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

    return (
        query
        .order_by(
            PatientVitals.recorded_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )