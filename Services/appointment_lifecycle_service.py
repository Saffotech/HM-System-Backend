"""Appointment lifecycle — close past open appointments as cancelled."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit
from Services.opd_helpers import IST, today_ist_date
from Services.queue_helpers import persist, status_value

# Still open after the appointment day → auto-cancel (not left scheduled/pending).
_PAST_OPEN_STATUSES = (AppointmentStatus.scheduled,)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def mark_past_open_appointments_cancelled(
    db: Session,
    *,
    as_of: Optional[date] = None,
    commit: bool = True,
) -> int:
    """
    Past calendar days (before ``as_of``, default today IST): any still-``scheduled``
    appointment becomes ``cancelled``. Completed rows are left alone.

    Linked open queue rows are cancelled as well so boards stay consistent.
    """
    cutoff_day = as_of or today_ist_date()
    cutoff = _day_start(cutoff_day)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.scheduled_at < cutoff,
            Appointment.status.in_(_PAST_OPEN_STATUSES),
        )
        .with_for_update()
        .all()
    )
    if not appointments:
        return 0

    appointment_ids = [apt.id for apt in appointments]
    for apt in appointments:
        apt.status = AppointmentStatus.cancelled

    if appointment_ids:
        paid_visit_rows = (
            db.query(OpdVisit.appointment_id)
            .filter(
                OpdVisit.appointment_id.in_(appointment_ids),
                OpdVisit.payment_status == "paid",
            )
            .all()
        )
        paid_appointment_ids = {row[0] for row in paid_visit_rows if row[0] is not None}
        if paid_appointment_ids:
            from Models.patient import Patient
            from Services.opd_notification_helpers import notify_opd_appointment_no_show

            for apt in appointments:
                if apt.id not in paid_appointment_ids:
                    continue
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                patient_name = (
                    f"{patient.first_name or ''} {patient.last_name or ''}".strip()
                    if patient
                    else "Patient"
                )
                notify_opd_appointment_no_show(
                    db,
                    apt,
                    patient_name=patient_name,
                )

    queues = (
        db.query(PatientQueue)
        .filter(PatientQueue.appointment_id.in_(appointment_ids))
        .with_for_update()
        .all()
    )
    for queue in queues:
        if status_value(queue.status) == QueueStatus.SCHEDULED.value:
            queue.status = QueueStatus.CANCELLED

    persist(db, commit=commit)
    return len(appointments)


# Back-compat alias used by older imports / scripts.
def mark_past_appointments_no_show(
    db: Session,
    *,
    as_of: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        cutoff_day = as_of or today_ist_date()
        cutoff = _day_start(cutoff_day)
        ids = [
            apt.id
            for apt in db.query(Appointment)
            .filter(
                Appointment.scheduled_at < cutoff,
                Appointment.status.in_(_PAST_OPEN_STATUSES),
            )
            .all()
        ]
        return {
            "dry_run": True,
            "as_of": cutoff_day.isoformat(),
            "matched": len(ids),
            "updated": 0,
            "appointment_ids": ids,
        }

    updated = mark_past_open_appointments_cancelled(db, as_of=as_of, commit=True)
    return {
        "dry_run": False,
        "as_of": (as_of or today_ist_date()).isoformat(),
        "matched": updated,
        "updated": updated,
        "appointment_ids": [],
    }
