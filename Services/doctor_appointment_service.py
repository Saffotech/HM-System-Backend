from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, AppointmentStatus
from Models.ipd import IpdAdmission
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.doctor_patient_queue_service import (
    complete_queue_for_appointment_if_exists,
)
from Services.queue_helpers import persist

# Doctor may complete or cancel. Past unconsulted are system-cancelled.
VALID_TRANSITIONS = {
    "scheduled": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
    "no_show": [],
}


def mark_past_scheduled_as_cancelled(
    db: Session,
    *,
    as_of: date | None = None,
    commit: bool = True,
) -> int:
    """Past open (scheduled) appointments become cancelled after the day ends."""
    from Services.appointment_lifecycle_service import (
        mark_past_open_appointments_cancelled,
    )

    return mark_past_open_appointments_cancelled(db, as_of=as_of, commit=commit)


# Back-compat for older call sites / imports.
def mark_past_scheduled_as_no_show(
    db: Session,
    *,
    as_of: date | None = None,
    commit: bool = True,
) -> int:
    return mark_past_scheduled_as_cancelled(db, as_of=as_of, commit=commit)


def _doctor_appointments_query(db: Session, doctor_id: int):
    """Doctor-visible appointments only — excludes no_show (DB-only status)."""
    return db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status != AppointmentStatus.no_show,
    )


def get_today_appointments_service(db: Session, doctor_id: int) -> list[dict]:
    try:
        mark_past_scheduled_as_no_show(db)
    except Exception:
        # Never block today's list if no-show backfill fails (enum/schema drift).
        db.rollback()
    today = opd_helpers.today_ist_date()
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(h.scheduled_on_date(today))
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    opd_items = h.appointments_to_dicts(db, rows)
    opd_patient_ids = {item.get("patient_id") for item in opd_items if item.get("patient_id")}

    try:
        admissions = (
            db.query(IpdAdmission)
            .filter(
                IpdAdmission.doctor_id == doctor_id,
                IpdAdmission.status == "admitted",
            )
            .order_by(IpdAdmission.admitted_at.desc())
            .all()
        )
        ipd_items = [
            item
            for item in h.admissions_to_dicts(
                db, admissions, use_dashboard_status=True
            )
            if item.get("patient_id") not in opd_patient_ids
        ]
    except Exception:
        db.rollback()
        ipd_items = []
    return opd_items + ipd_items


def get_appointment_by_id_service(db: Session, appointment_id: int, doctor_id: int) -> dict:
    apt = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return h.appointment_to_dict(db, apt)


def _status_value(status) -> str:
    return getattr(status, "value", status)


def update_appointment_status_service(
    db: Session,
    appointment_id: int,
    doctor_id: int,
    status: str,
) -> dict:
    status = getattr(status, "value", status)
    if status == AppointmentStatus.no_show.value:
        raise HTTPException(
            status_code=400,
            detail="no_show is system-managed and cannot be set from the doctor API",
        )

    apt = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.id == appointment_id)
        .with_for_update()
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current = _status_value(apt.status)
    allowed = VALID_TRANSITIONS.get(current, [])
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change appointment status from {current} to {status}",
        )

    if status == AppointmentStatus.completed.value:
        queue = complete_queue_for_appointment_if_exists(
            db,
            appointment_id,
            apt,
            updated_by=doctor_id,
        )
        if not queue:
            apt.status = status
    else:
        apt.status = status

    persist(db)
    db.refresh(apt)
    return h.appointment_to_dict(db, apt)


def get_appointment_history_service(
    db: Session,
    doctor_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)

    query = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.status == AppointmentStatus.completed)
    )
    total = query.count()
    rows = (
        query.order_by(Appointment.scheduled_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    appointments = h.appointments_to_dicts(db, rows)
    return {
        "success": True,
        "message": "Appointment history fetched successfully",
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": appointments,
        # Legacy keys for existing doctor clients
        "total_appointments": total,
        "appointments": appointments,
    }


def get_appointments_by_date_service(
    db: Session,
    doctor_id: int,
    appointment_date: date,
) -> list[dict]:
    try:
        mark_past_scheduled_as_no_show(db)
    except Exception:
        db.rollback()
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(h.scheduled_on_date(appointment_date))
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return h.appointments_to_dicts(db, rows)
