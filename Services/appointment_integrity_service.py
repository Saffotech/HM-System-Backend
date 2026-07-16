"""One-time cleanup helpers for legacy duplicate OPD appointments."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit
from Services import opd_helpers as h
from Services.appointment_service import _to_ist


_CANCEL_NOTE = "[auto-cancelled: duplicate appointment]"
_ACTIVE_REUSE_STATUSES = (
    AppointmentStatus.scheduled,
    AppointmentStatus.waiting,
    AppointmentStatus.in_progress,
)


def _group_key(apt: Appointment) -> tuple:
    day = _to_ist(apt.scheduled_at).date() if apt.scheduled_at else None
    return (apt.patient_id, apt.doctor_id, apt.department_id, day)


def _rank_canonical(
    apt: Appointment,
    visit_by_apt: dict[int, OpdVisit],
) -> tuple:
    """Higher rank wins. Prefer paid visit, any visit, later slot, higher id."""
    visit = visit_by_apt.get(apt.id)
    paid = 1 if visit and visit.payment_status == "paid" else 0
    linked = 1 if visit else 0
    ts = _to_ist(apt.scheduled_at).timestamp() if apt.scheduled_at else 0.0
    return (paid, linked, ts, apt.id)


def _load_visits_by_appointment(
    db: Session, appointment_ids: Iterable[int]
) -> dict[int, OpdVisit]:
    ids = list(appointment_ids)
    if not ids:
        return {}
    rows = (
        db.query(OpdVisit)
        .filter(
            OpdVisit.appointment_id.in_(ids),
            OpdVisit.status != "cancelled",
        )
        .order_by(OpdVisit.id.desc())
        .all()
    )
    out: dict[int, OpdVisit] = {}
    for visit in rows:
        if visit.appointment_id is not None and visit.appointment_id not in out:
            out[visit.appointment_id] = visit
    return out


def cleanup_duplicate_active_appointments(
    db: Session,
    *,
    dry_run: bool = False,
) -> dict:
    """
    Cancel duplicate active appointments for the same patient+doctor+dept+day.

    Keeps the canonical appointment (paid linked visit preferred), remaps any
    visits/queue rows from cancelled duplicates onto the kept appointment, and
    never deletes payment or visit rows.
    """
    active = (
        db.query(Appointment)
        .filter(Appointment.status.in_(_ACTIVE_REUSE_STATUSES))
        .order_by(Appointment.id.asc())
        .all()
    )

    groups: dict[tuple, list[Appointment]] = defaultdict(list)
    for apt in active:
        groups[_group_key(apt)].append(apt)

    visit_by_apt = _load_visits_by_appointment(db, [a.id for a in active])
    cancelled_ids: list[int] = []
    kept_ids: list[int] = []
    remapped_visits = 0
    remapped_queues = 0

    for key, group in groups.items():
        if key[3] is None or len(group) < 2:
            continue

        keep = max(group, key=lambda a: _rank_canonical(a, visit_by_apt))
        kept_ids.append(keep.id)
        duplicates = [a for a in group if a.id != keep.id]

        for dup in duplicates:
            # Remap visits onto the canonical appointment.
            visits = (
                db.query(OpdVisit)
                .filter(OpdVisit.appointment_id == dup.id)
                .all()
            )
            for visit in visits:
                visit.appointment_id = keep.id
                remapped_visits += 1

            queues = (
                db.query(PatientQueue)
                .filter(PatientQueue.appointment_id == dup.id)
                .all()
            )
            for queue in queues:
                # Skip if canonical already has a queue row same day+doctor.
                clash = (
                    db.query(PatientQueue)
                    .filter(
                        PatientQueue.appointment_id == keep.id,
                        PatientQueue.queue_date == queue.queue_date,
                    )
                    .first()
                )
                if clash:
                    # Prefer keeping canonical queue; leave orphan queue linked
                    # until ops decide — do not delete history.
                    continue
                queue.appointment_id = keep.id
                queue.appointment_uid = keep.appointment_uid
                remapped_queues += 1

            note = (dup.notes or "").strip()
            if _CANCEL_NOTE not in note:
                dup.notes = f"{note} {_CANCEL_NOTE}".strip() if note else _CANCEL_NOTE
            dup.status = AppointmentStatus.cancelled
            cancelled_ids.append(dup.id)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "dry_run": dry_run,
        "as_of": h.now_ist().isoformat(),
        "groups_with_duplicates": sum(
            1 for key, g in groups.items() if key[3] is not None and len(g) > 1
        ),
        "kept_appointment_ids": kept_ids,
        "cancelled_appointment_ids": cancelled_ids,
        "cancelled": len(cancelled_ids),
        "remapped_visits": remapped_visits,
        "remapped_queues": remapped_queues,
    }
