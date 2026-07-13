"""Auto-enqueue patients after OPD payment."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue
from Models.opd_billing import Appointment
from Models.patient import OpdVisit
from Services.queue_helpers import is_appointment_active, is_visit_paid


def _get_linked_appointment(
    db: Session,
    visit: OpdVisit,
) -> Appointment | None:
    """Return linked appointment only — never auto-create a walk-in."""
    if not visit.appointment_id:
        return None

    apt = db.query(Appointment).filter(Appointment.id == visit.appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Linked appointment not found")
    return apt


def enqueue_after_payment_if_eligible(
    db: Session,
    visit: OpdVisit,
    *,
    handled_by: int | None = None,
) -> PatientQueue | None:
    """
    After successful payment, create patient_queue row for the linked appointment.
    Returns None if not yet paid, or if no appointment is linked yet
    (appointment must be booked explicitly via POST /opd/appointments).
    """
    if not is_visit_paid(visit):
        return None

    appointment = _get_linked_appointment(db, visit)
    if appointment is None:
        return None
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
