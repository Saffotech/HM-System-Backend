"""Appointment lifecycle — mark past open appointments as no_show."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, AppointmentStatus
from Services.opd_helpers import IST, today_ist_date

# Still open after the appointment day → treat as missed (not cancelled).
_PAST_OPEN_STATUSES = (AppointmentStatus.scheduled,)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def mark_past_appointments_no_show(
    db: Session,
    *,
    as_of: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    """
    Set status=no_show for appointments whose scheduled day is before `as_of`
    (default: today in Asia/Kolkata) and that are still scheduled.

    Does not touch completed, cancelled, or already no_show.
    """
    cutoff_day = as_of or today_ist_date()
    cutoff = _day_start(cutoff_day)

    rows = (
        db.query(Appointment)
        .filter(
            Appointment.scheduled_at < cutoff,
            Appointment.status.in_(_PAST_OPEN_STATUSES),
        )
        .order_by(Appointment.scheduled_at.asc(), Appointment.id.asc())
        .all()
    )

    ids = [apt.id for apt in rows]
    if dry_run:
        return {
            "dry_run": True,
            "as_of": cutoff_day.isoformat(),
            "matched": len(ids),
            "updated": 0,
            "appointment_ids": ids,
        }

    for apt in rows:
        apt.status = AppointmentStatus.no_show

    if rows:
        db.commit()

    return {
        "dry_run": False,
        "as_of": cutoff_day.isoformat(),
        "matched": len(ids),
        "updated": len(ids),
        "appointment_ids": ids,
    }
