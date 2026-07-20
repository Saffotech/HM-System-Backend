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
    """Return linked appointment; self-heal orphan visits via same-day match."""
    from Services.appointment_service import link_orphan_visit_to_appointment

    return link_orphan_visit_to_appointment(db, visit)


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
        # 409 = already queued; 400 = not eligible yet — never break payment/list flows
        if exc.status_code in {400, 409}:
            return find_queue_for_appointment_today(db, appointment.id)
        raise
