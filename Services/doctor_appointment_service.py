from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, AppointmentStatus
from Services import doctor_helpers as h

VALID_TRANSITIONS = {
    "scheduled": ["waiting", "cancelled"],
    "waiting": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}


def _doctor_appointments_query(db: Session, doctor_id: int):
    return db.query(Appointment).filter(Appointment.doctor_id == doctor_id)


def get_today_appointments_service(db: Session, doctor_id: int) -> list[dict]:
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(h.scheduled_on_date(date.today()))
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return h.appointments_to_dicts(db, rows)


def get_appointment_by_id_service(db: Session, appointment_id: int, doctor_id: int) -> dict:
    apt = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return h.appointment_to_dict(db, apt)


def update_appointment_status_service(
    db: Session,
    appointment_id: int,
    doctor_id: int,
    status: str,
) -> dict:
    status = getattr(status, "value", status)
    apt = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    allowed = VALID_TRANSITIONS.get(apt.status, [])
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change appointment status from {apt.status} to {status}",
        )

    apt.status = status
    db.commit()
    db.refresh(apt)
    return h.appointment_to_dict(db, apt)


def get_appointment_history_service(db: Session, doctor_id: int) -> list[dict]:
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.status == AppointmentStatus.completed)
        .order_by(Appointment.scheduled_at.desc())
        .all()
    )
    return h.appointments_to_dicts(db, rows)


def get_appointments_by_date_service(
    db: Session,
    doctor_id: int,
    appointment_date: date,
) -> list[dict]:
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(h.scheduled_on_date(appointment_date))
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return h.appointments_to_dicts(db, rows)


def get_dashboard_stats_service(db: Session, doctor_id: int) -> dict:
    today_filter = h.scheduled_on_date(date.today())
    base = _doctor_appointments_query(db, doctor_id).filter(today_filter)

    return {
        "today_appointments": base.count(),
        "patients_waiting": base.filter(Appointment.status == "waiting").count(),
        "patients_in_progress": base.filter(Appointment.status == "in_progress").count(),
        "completed_consultations": base.filter(Appointment.status == "completed").count(),
        "cancelled_appointments": base.filter(Appointment.status == "cancelled").count(),
    }
