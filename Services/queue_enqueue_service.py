"""Auto-enqueue patients after OPD payment."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue
from Models.opd_billing import Appointment
from Models.patient import OpdVisit
from Services import appointment_service
from Services.queue_helpers import is_appointment_active, is_visit_paid


def _ensure_visit_appointment(
    db: Session,
    visit: OpdVisit,
    *,
    created_by: int | None,
) -> Appointment:
    if visit.appointment_id:
        apt = db.query(Appointment).filter(Appointment.id == visit.appointment_id).first()
        if not apt:
            raise HTTPException(status_code=404, detail="Linked appointment not found")
        return apt

    if not visit.doctor_id:
        raise HTTPException(
            status_code=400,
            detail="Visit has no doctor; cannot create appointment for queue",
        )

    apt = appointment_service.create_walk_in_appointment(
        db,
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        department_id=visit.department_id,
        created_by=created_by or visit.registered_by or 0,
    )
    visit.appointment_id = apt.id
    db.flush()
    return apt


def enqueue_after_payment_if_eligible(
    db: Session,
    visit: OpdVisit,
    *,
    handled_by: int | None = None,
) -> PatientQueue | None:
    """
    After successful payment, create patient_queue row for the linked appointment.
    Returns None if not yet paid; returns existing or new queue row when enqueued.
    """
    if not is_visit_paid(visit):
        return None

    appointment = _ensure_visit_appointment(db, visit, created_by=handled_by)
    if not is_appointment_active(appointment):
        return None

    # Lazy import avoids circular dependency with doctor_patient_queue_service.
    from Services.doctor_patient_queue_service import (
        add_patient_to_queue_service,
        find_queue_for_appointment_today,
    )

    existing = find_queue_for_appointment_today(db, appointment.id)
    if existing:
        return existing

    try:
        return add_patient_to_queue_service(
            db,
            appointment.id,
            created_by=handled_by,
        )
    except HTTPException as exc:
        if exc.status_code == 409:
            return find_queue_for_appointment_today(db, appointment.id)
        raise
