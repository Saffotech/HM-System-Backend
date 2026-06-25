from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.nurse_patient_vitals import PatientVitals
from Models.doctor_patient_queue import PatientQueue

from Schemas.nurse_schema import (
    VitalCreate,
    VitalUpdate,
    VitalResponse,
)
from Services.nurse_emergency_alert_triggers import process_vital_alerts

IST = ZoneInfo("Asia/Kolkata")


def _serialize_vital(vital: PatientVitals) -> VitalResponse:
    return VitalResponse.model_validate(vital).model_copy(
        update={
            "patient_uid": (
                vital.patient.patient_uid if vital.patient else None
            )
        }
    )


def _vital_query(db: Session):
    return db.query(PatientVitals).options(
        joinedload(PatientVitals.patient)
    )


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
        vital = (
            _vital_query(db)
            .filter(PatientVitals.id == vital.id)
            .first()
        )

        process_vital_alerts(
            db=db,
            vital=vital,
            nurse_id=nurse_id,
            mark_critical=bool(vital_data.mark_critical),
        )

        return _serialize_vital(vital)

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

        mark_critical = bool(
            update_data.pop("mark_critical", False)
        )

        for field, value in update_data.items():
            setattr(vital, field, value)

        vital.updated_at = datetime.now(IST)

        db.commit()
        db.refresh(vital)
        vital = (
            _vital_query(db)
            .filter(PatientVitals.id == vital.id)
            .first()
        )

        process_vital_alerts(
            db=db,
            vital=vital,
            nurse_id=nurse_id,
            mark_critical=mark_critical,
        )

        return _serialize_vital(vital)

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

    return _serialize_vital(vital)


# ==========================================================
# GET ALL VITALS
# ==========================================================

def get_all_vitals_service(
    db: Session,
    page: int = 1,
    page_size: int = 20
):

    vitals = (
        _vital_query(db)
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

    return [_serialize_vital(vital) for vital in vitals]


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

    page: int = 1,
    page_size: int = 20
):

    query = (
        _vital_query(db)
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

    vitals = (
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

    return [_serialize_vital(vital) for vital in vitals]