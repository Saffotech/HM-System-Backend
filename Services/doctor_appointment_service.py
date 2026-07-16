from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Schemas.doctor_appointment_schema import AppointmentConsultationUpdate
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.doctor_patient_queue_service import (
    _apply_clinical_to_appointment,
    complete_queue_for_appointment_if_exists,
    queue_to_summary,
)
from Services.queue_helpers import persist, status_value

IST = opd_helpers.IST

# Doctor may only complete. Cancel is OPD; no_show is system-managed.
VALID_TRANSITIONS = {
    "scheduled": ["completed"],
    "completed": [],
    "cancelled": [],
    "no_show": [],
}


def mark_past_scheduled_as_no_show(
    db: Session,
    *,
    as_of: date | None = None,
    commit: bool = True,
) -> int:
    """
    System-only: past ``scheduled`` appointments become ``no_show`` in DB.
    Frontend/doctor APIs never list these patients.
    """
    cutoff_date = as_of or opd_helpers.today_ist_date()
    cutoff_start = datetime.combine(cutoff_date, time.min, tzinfo=IST)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.status == AppointmentStatus.scheduled,
            Appointment.scheduled_at < cutoff_start,
        )
        .with_for_update()
        .all()
    )
    if not appointments:
        return 0

    appointment_ids = [apt.id for apt in appointments]
    for apt in appointments:
        apt.status = AppointmentStatus.no_show

    queues = (
        db.query(PatientQueue)
        .filter(PatientQueue.appointment_id.in_(appointment_ids))
        .with_for_update()
        .all()
    )
    for queue in queues:
        if status_value(queue.status) == QueueStatus.SCHEDULED.value:
            queue.status = QueueStatus.NO_SHOW

    persist(db, commit=commit)
    return len(appointments)


def _doctor_appointments_query(db: Session, doctor_id: int):
    """Doctor-visible appointments only — excludes no_show (DB-only status)."""
    return db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status != AppointmentStatus.no_show,
    )


def get_today_appointments_service(db: Session, doctor_id: int) -> list[dict]:
    mark_past_scheduled_as_no_show(db)
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


def _status_value(status) -> str:
    return getattr(status, "value", status)


def _clinical_from_appointment_update(
    data: AppointmentConsultationUpdate,
) -> CompleteConsultationSchema:
    return CompleteConsultationSchema(
        symptoms=data.symptoms,
        diagnosis=data.diagnosis,
        notes=data.notes,
        follow_up_date=data.follow_up_date,
    )


def complete_appointment_consultation_service(
    db: Session,
    appointment_id: int,
    doctor_id: int,
    clinical: AppointmentConsultationUpdate,
) -> dict:
    """
    Queue-optional consultation save:
    scheduled → completed with clinical fields.
    Updates patient_queue only if a row already exists today.
    """
    appointment = (
        _doctor_appointments_query(db, doctor_id)
        .filter(Appointment.id == appointment_id)
        .with_for_update()
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current = _status_value(appointment.status)
    if current == AppointmentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Consultation already completed")
    if current == AppointmentStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="Cannot save consultation for cancelled appointment")

    allowed = VALID_TRANSITIONS.get(current, [])
    if AppointmentStatus.completed.value not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete consultation from appointment status {current}",
        )

    clinical_payload = _clinical_from_appointment_update(clinical)
    queue = complete_queue_for_appointment_if_exists(
        db,
        appointment_id,
        appointment,
        clinical=clinical_payload,
        updated_by=doctor_id,
    )

    if not queue:
        _apply_clinical_to_appointment(appointment, clinical_payload)
        appointment.status = AppointmentStatus.completed

    persist(db)
    db.refresh(appointment)
    if queue:
        db.refresh(queue)

    return {
        "success": True,
        "message": "Consultation saved",
        "appointment": h.appointment_to_dict(db, appointment),
        "queue": queue_to_summary(queue) if queue else None,
    }


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
    mark_past_scheduled_as_no_show(db)
    rows = (
        _doctor_appointments_query(db, doctor_id)
        .filter(h.scheduled_on_date(appointment_date))
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return h.appointments_to_dicts(db, rows)


def get_dashboard_stats_service(db: Session, doctor_id: int) -> dict:
    mark_past_scheduled_as_no_show(db)
    today_filter = h.scheduled_on_date(date.today())
    base = _doctor_appointments_query(db, doctor_id).filter(today_filter)

    return {
        "today_appointments": base.count(),
        "patients_scheduled": base.filter(Appointment.status == "scheduled").count(),
        "completed_consultations": base.filter(Appointment.status == "completed").count(),
        "cancelled_appointments": base.filter(Appointment.status == "cancelled").count(),
    }
