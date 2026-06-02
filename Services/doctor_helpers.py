"""Shared helpers for doctor module (OPD appointments + patients)."""
from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.opd_billing import Appointment
from Models.patient import Patient

IST = ZoneInfo("Asia/Kolkata")


def day_bounds(on_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(on_date, time.min, tzinfo=IST)
    end = datetime.combine(on_date, time.max, tzinfo=IST)
    return start, end


def scheduled_on_date(on_date: date):
    start, end = day_bounds(on_date)
    return and_(Appointment.scheduled_at >= start, Appointment.scheduled_at <= end)


def display_name(first: str, last: Optional[str] = None) -> str:
    return f"{first} {last or ''}".strip()


def patient_age(date_of_birth: Optional[date]) -> Optional[int]:
    if not date_of_birth:
        return None
    today = date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
    return (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active.is_(True))
        .first()
    )


def appointment_to_dict(
    db: Session,
    apt: Appointment,
    patient: Optional[Patient] = None,
) -> dict:
    if patient is None:
        patient = get_patient(db, apt.patient_id)

    scheduled = apt.scheduled_at
    return {
        "id": apt.id,
        "appointment_uid": apt.appointment_uid,
        "patient_id": apt.patient_id,
        "patient_name": display_name(patient.first_name, patient.last_name) if patient else "",
        "patient_phone": patient.phone if patient else "",
        "patient_age": patient_age(patient.date_of_birth) if patient else None,
        "patient_gender": patient.gender if patient else None,
        "patient_uhid": patient.patient_uid if patient else "",
        "doctor_id": apt.doctor_id,
        "department_id": apt.department_id,
        "scheduled_at": scheduled.isoformat() if scheduled else None,
        "appointment_date": scheduled.date().isoformat() if scheduled else None,
        "appointment_time": scheduled.strftime("%H:%M:%S") if scheduled else None,
        "appointment_type": apt.appointment_type,
        "status": apt.status,
        "reason": apt.reason,
        "notes": apt.notes,
        "created_at": apt.created_at.isoformat() if apt.created_at else None,
    }


def appointments_to_dicts(db: Session, rows: List[Appointment]) -> List[dict]:
    patient_cache: dict[int, Patient] = {}
    out = []
    for apt in rows:
        pid = apt.patient_id
        if pid not in patient_cache:
            patient_cache[pid] = get_patient(db, pid)
        out.append(appointment_to_dict(db, apt, patient_cache.get(pid)))
    return out
