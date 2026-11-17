"""Nurse Workforce Management — shifts, roster, and dashboard."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.department import Department
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_workforce import (
    NurseWorkforceRoster,
    NurseWorkforceShift,
)
from Models.opd_billing import Bed
from Models.role import Role
from Models.user import User
from Schemas.nurse_workforce_schema import (
    NurseWorkforceRosterBulkCreate,
    NurseWorkforceRosterCreate,
    NurseWorkforceShiftCreate,
    NurseWorkforceShiftUpdate,
)
from Services.notification_service import create_notification

IST = ZoneInfo("Asia/Kolkata")

DEFAULT_SHIFTS = [
    ("Morning", "MORNING", time(6, 0), time(14, 0), "#F59E0B"),
    ("Evening", "EVENING", time(14, 0), time(22, 0), "#3B82F6"),
    ("Night", "NIGHT", time(22, 0), time(6, 0), "#6366F1"),
]

def _now() -> datetime:
    return datetime.now(IST)


def _shift_end_at(roster_date: date, start_time: time, end_time: time) -> datetime:
    """Instant the assignment finishes, from the shift's configured times.

    When the end time is not after the start time, the shift crosses midnight
    and finishes on the next calendar day (for example 22:00–06:00).
    """
    start = start_time.replace(tzinfo=None)
    end = end_time.replace(tzinfo=None)
    end_date = roster_date if end > start else roster_date + timedelta(days=1)
    return datetime.combine(end_date, end, tzinfo=IST)


def _shift_has_ended(roster_date: date, start_time: time, end_time: time) -> bool:
    return _now() >= _shift_end_at(roster_date, start_time, end_time)


def complete_finished_roster_entries(db: Session, *, commit: bool = True) -> int:
    """Apply the roster lifecycle: scheduled, then completed once the shift ends.

    New assignments are scheduled. This marks one completed when the current
    time reaches the shift's configured end. Any leftover confirmed row is
    moved to scheduled, or to completed if that shift has already ended.
    Cancelled rows are left as they are.
    """
    now = _now()
    rows = (
        db.query(NurseWorkforceRoster, NurseWorkforceShift)
        .join(NurseWorkforceShift, NurseWorkforceShift.id == NurseWorkforceRoster.shift_id)
        .filter(
            or_(
                NurseWorkforceRoster.status == "confirmed",
                and_(
                    NurseWorkforceRoster.status == "scheduled",
                    NurseWorkforceRoster.roster_date <= now.date(),
                ),
            )
        )
        .all()
    )
    changed = 0
    for roster, shift in rows:
        finished = now >= _shift_end_at(roster.roster_date, shift.start_time, shift.end_time)
        next_status = "completed" if finished else "scheduled"
        if roster.status != next_status:
            roster.status = next_status
            roster.updated_at = now
            changed += 1
    if changed:
        if commit:
            db.commit()
        else:
            db.flush()
    return changed


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    return " ".join(
        p for p in [(user.first_name or "").strip(), (user.last_name or "").strip()] if p
    ) or (user.email or f"User #{user.id}")


def _require_nurse(db: Session, nurse_id: int) -> User:
    user = (
        db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(User.id == nurse_id, User.deleted_at.is_(None), Role.name == "nurse")
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Selected user is not an active nurse")
    if user.is_active is False:
        raise HTTPException(status_code=400, detail="Selected nurse is inactive")
    return user


def _session_tenant_id(db: Session) -> int | None:
    return db.info.get("tenant_id")


def _find_roster_row(
    db: Session,
    *,
    nurse_id: int,
    roster_date: date,
    shift_id: int,
) -> NurseWorkforceRoster | None:
    """Find the unique roster slot even when its hospital id was never stamped."""
    return (
        db.query(NurseWorkforceRoster)
        .execution_options(include_all_tenants=True)
        .filter(
            NurseWorkforceRoster.nurse_id == nurse_id,
            NurseWorkforceRoster.roster_date == roster_date,
            NurseWorkforceRoster.shift_id == shift_id,
        )
        .first()
    )


def _reactivate_roster_row(
    db: Session,
    row: NurseWorkforceRoster,
    *,
    department_id: int | None,
    notes: str | None,
    assigned_by: int,
    status: str = "scheduled",
) -> NurseWorkforceRoster:
    row.status = status or "scheduled"
    row.department_id = department_id
    row.notes = notes
    row.assigned_by = assigned_by
    row.updated_at = _now()
    tenant_id = _session_tenant_id(db)
    if tenant_id is not None and row.tenant_id is None:
        row.tenant_id = tenant_id
    return row


def _notify_nurse(
    db: Session,
    *,
    nurse_id: int,
    title: str,
    message: str,
    actor: User | None,
    reference_type: ReferenceType,
    reference_id: int | None,
    notification_type: NotificationType = NotificationType.SHIFT_UPDATED,
    priority: NotificationPriority = NotificationPriority.NORMAL,
) -> None:
    try:
        create_notification(
            db,
            user_id=nurse_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=SourceModule.ADMIN,
            reference_type=reference_type,
            reference_id=reference_id if reference_id is not None else nurse_id,
            created_by=actor.id if actor else None,
            created_by_name=_display_name(actor) if actor else "Admin",
            priority=priority,
        )
    except Exception:
        # The roster row is already committed. Clear the failed notification
        # transaction so this request can still finish.
        db.rollback()


# =========================================================
# Shift master
# =========================================================

def ensure_default_shifts_service(db: Session) -> dict:
    created = 0
    for name, code, start, end, color in DEFAULT_SHIFTS:
        exists = (
            db.query(NurseWorkforceShift)
            .filter(NurseWorkforceShift.name == name)
            .first()
        )
        if exists:
            continue
        db.add(
            NurseWorkforceShift(
                name=name,
                code=code,
                start_time=start,
                end_time=end,
                grace_minutes=15,
                color=color,
                is_active=True,
                is_template=True,
                weekly_mask="1111111",
            )
        )
        created += 1
    if created:
        db.commit()
    return {"success": True, "created": created}


def _shift_out(row: NurseWorkforceShift) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "grace_minutes": row.grace_minutes,
        "color": row.color,
        "is_active": row.is_active,
        "is_template": row.is_template,
        "weekly_mask": row.weekly_mask,
        "notes": row.notes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_shifts_service(db: Session, *, is_active: bool | None = True) -> dict:
    ensure_default_shifts_service(db)
    q = db.query(NurseWorkforceShift)
    if is_active is not None:
        q = q.filter(NurseWorkforceShift.is_active.is_(is_active))
    rows = q.order_by(NurseWorkforceShift.start_time.asc()).all()
    return {"success": True, "total": len(rows), "items": [_shift_out(r) for r in rows]}


def _clock_minutes(value: time) -> int:
    clock = value.replace(tzinfo=None)
    return clock.hour * 60 + clock.minute


def _format_shift_clock(value: time) -> str:
    clock = value.replace(tzinfo=None)
    return f"{clock.hour:02d}:{clock.minute:02d}"


def _shift_intervals(start_time: time, end_time: time) -> list[tuple[int, int]]:
    """Half-open minute ranges covered by a shift.

    A shift that ends at the next shift's start does not overlap it.
    A shift whose end is not after its start crosses midnight.
    """
    start = _clock_minutes(start_time)
    end = _clock_minutes(end_time)
    if start < end:
        return [(start, end)]
    if start > end:
        return [(start, 24 * 60), (0, end)]
    return [(0, 24 * 60)]


def _intervals_overlap(
    left: list[tuple[int, int]],
    right: list[tuple[int, int]],
) -> bool:
    return any(start_a < end_b and start_b < end_a for start_a, end_a in left for start_b, end_b in right)


def _reject_overlapping_shift(
    db: Session,
    start_time: time,
    end_time: time,
    *,
    exclude_id: int | None = None,
) -> None:
    """Active shifts must not cover the same part of the day."""
    incoming = _shift_intervals(start_time, end_time)
    rows = (
        db.query(NurseWorkforceShift)
        .filter(NurseWorkforceShift.is_active.is_(True))
        .order_by(NurseWorkforceShift.start_time.asc())
        .all()
    )
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if not _intervals_overlap(incoming, _shift_intervals(row.start_time, row.end_time)):
            continue
        raise HTTPException(
            status_code=400,
            detail=(
                "Shift timings overlap an existing shift "
                f"({row.name}, {_format_shift_clock(row.start_time)}–{_format_shift_clock(row.end_time)})."
            ),
        )


def create_shift_service(db: Session, data: NurseWorkforceShiftCreate) -> dict:
    if db.query(NurseWorkforceShift).filter(NurseWorkforceShift.name == data.name.strip()).first():
        raise HTTPException(status_code=400, detail="Shift name already exists")
    if data.is_active:
        _reject_overlapping_shift(db, data.start_time, data.end_time)
    row = NurseWorkforceShift(
        name=data.name.strip(),
        code=(data.code or None),
        start_time=data.start_time,
        end_time=data.end_time,
        grace_minutes=data.grace_minutes,
        color=data.color,
        is_active=data.is_active,
        is_template=data.is_template,
        weekly_mask=data.weekly_mask,
        notes=data.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": _shift_out(row)}


def update_shift_service(db: Session, shift_id: int, data: NurseWorkforceShiftUpdate) -> dict:
    row = db.query(NurseWorkforceShift).filter(NurseWorkforceShift.id == shift_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Shift not found")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"]:
        payload["name"] = payload["name"].strip()
    start_time = payload.get("start_time") or row.start_time
    end_time = payload.get("end_time") or row.end_time
    is_active = payload["is_active"] if payload.get("is_active") is not None else row.is_active
    if is_active:
        _reject_overlapping_shift(
            db,
            start_time,
            end_time,
            exclude_id=row.id,
        )
    for key, value in payload.items():
        setattr(row, key, value)
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return {"success": True, "data": _shift_out(row)}


def delete_shift_service(db: Session, shift_id: int) -> dict:
    row = db.query(NurseWorkforceShift).filter(NurseWorkforceShift.id == shift_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Shift not found")
    row.is_active = False
    row.updated_at = _now()
    db.commit()
    return {"success": True, "data": _shift_out(row)}


# =========================================================
# Roster
# =========================================================

def _roster_out(db: Session, row: NurseWorkforceRoster) -> dict:
    nurse = db.query(User).filter(User.id == row.nurse_id).first()
    shift = db.query(NurseWorkforceShift).filter(NurseWorkforceShift.id == row.shift_id).first()
    dept = (
        db.query(Department).filter(Department.id == row.department_id).first()
        if row.department_id
        else None
    )
    return {
        "id": row.id,
        "nurse_id": row.nurse_id,
        "nurse_name": _display_name(nurse),
        "shift_id": row.shift_id,
        "shift_name": shift.name if shift else None,
        "shift_color": shift.color if shift else None,
        "start_time": shift.start_time if shift else None,
        "end_time": shift.end_time if shift else None,
        "department_id": row.department_id,
        "department_name": dept.name if dept else None,
        "roster_date": row.roster_date,
        "status": row.status,
        "notes": row.notes,
        "assigned_by": row.assigned_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_roster_service(
    db: Session,
    data: NurseWorkforceRosterCreate,
    *,
    assigned_by: int,
    actor: User | None = None,
) -> dict:
    nurse = _require_nurse(db, data.nurse_id)
    shift = db.query(NurseWorkforceShift).filter(NurseWorkforceShift.id == data.shift_id).first()
    if not shift or not shift.is_active:
        raise HTTPException(status_code=400, detail="Shift not found or inactive")
    if _shift_has_ended(data.roster_date, shift.start_time, shift.end_time):
        raise HTTPException(
            status_code=400,
            detail="Cannot assign a shift after it has already ended.",
        )
    if data.department_id is not None:
        if not db.query(Department).filter(Department.id == data.department_id).first():
            raise HTTPException(status_code=404, detail="Department not found")

    existing = _find_roster_row(
        db,
        nurse_id=nurse.id,
        roster_date=data.roster_date,
        shift_id=shift.id,
    )
    if existing and existing.status != "cancelled":
        raise HTTPException(status_code=400, detail="Roster entry already exists")
    if existing:
        row = _reactivate_roster_row(
            db,
            existing,
            department_id=data.department_id,
            notes=data.notes,
            assigned_by=assigned_by,
            status="scheduled",
        )
    else:
        row = NurseWorkforceRoster(
            nurse_id=nurse.id,
            shift_id=shift.id,
            department_id=data.department_id,
            roster_date=data.roster_date,
            status="scheduled",
            notes=data.notes,
            assigned_by=assigned_by,
            tenant_id=_session_tenant_id(db),
        )
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Roster entry already exists") from None
    db.refresh(row)
    _notify_nurse(
        db,
        nurse_id=nurse.id,
        title="Shift assigned",
        message=f"You are rostered for {shift.name} on {data.roster_date}.",
        actor=actor,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=row.id,
        notification_type=NotificationType.SHIFT_UPDATED,
    )
    complete_finished_roster_entries(db)
    return {"success": True, "data": _roster_out(db, row)}



def bulk_create_roster_service(
    db: Session,
    data: NurseWorkforceRosterBulkCreate,
    *,
    assigned_by: int,
    actor: User | None = None,
) -> dict:
    shift = (
        db.query(NurseWorkforceShift)
        .filter(NurseWorkforceShift.id == data.shift_id)
        .first()
    )
    if not shift or not shift.is_active:
        raise HTTPException(
            status_code=400,
            detail="Shift not found or inactive",
        )

    created = []
    skipped = 0
    errors = []

    # Keep track of created entries separately for each nurse.
    created_by_nurse: dict[int, list[tuple[int, date]]] = {}

    try:
        for nurse_id in dict.fromkeys(data.nurse_ids):
            try:
                nurse = _require_nurse(db, nurse_id)
            except HTTPException as exc:
                errors.append(str(exc.detail))
                skipped += 1
                continue

            for roster_date in dict.fromkeys(data.dates):
                if _shift_has_ended(roster_date, shift.start_time, shift.end_time):
                    continue
                existing = _find_roster_row(
                    db,
                    nurse_id=nurse.id,
                    roster_date=roster_date,
                    shift_id=shift.id,
                )
                if existing and existing.status != "cancelled":
                    skipped += 1
                    continue
                if existing:
                    row = _reactivate_roster_row(
                        db,
                        existing,
                        department_id=data.department_id,
                        notes=data.notes,
                        assigned_by=assigned_by,
                    )
                    created.append(row.id)
                    created_by_nurse.setdefault(nurse.id, []).append(
                        (row.id, roster_date)
                    )
                    continue

                nested = db.begin_nested()
                try:
                    row = NurseWorkforceRoster(
                        nurse_id=nurse.id,
                        shift_id=shift.id,
                        department_id=data.department_id,
                        roster_date=roster_date,
                        status="scheduled",
                        notes=data.notes,
                        assigned_by=assigned_by,
                        tenant_id=_session_tenant_id(db),
                    )
                    db.add(row)
                    db.flush()
                    nested.commit()
                except IntegrityError:
                    nested.rollback()
                    skipped += 1
                    continue

                created.append(row.id)
                created_by_nurse.setdefault(nurse.id, []).append(
                    (row.id, roster_date)
                )

        # Save all roster entries before sending notifications.
        db.commit()

    except Exception:
        db.rollback()
        raise

    if not created and not skipped and not errors:
        raise HTTPException(
            status_code=400,
            detail="Cannot assign a shift after it has already ended.",
        )

    # IMPORTANT: one summary notification per nurse, outside both loops.
    for nurse_id, entries in created_by_nurse.items():
        roster_dates = [roster_date for _, roster_date in entries]
        start_date = min(roster_dates)
        end_date = max(roster_dates)

        if start_date == end_date:
            date_message = f"on {start_date:%d-%m-%Y}"
        else:
            date_message = (
                f"from {start_date:%d-%m-%Y} "
                f"to {end_date:%d-%m-%Y}"
            )

        _notify_nurse(
            db,
            nurse_id=nurse_id,
            title="Shift assigned",
            message=(
                f"You have been rostered for {shift.name} "
                f"for {len(entries)} date(s), {date_message}."
            ),
            actor=actor,
            reference_type=ReferenceType.SCHEDULE,
            reference_id=entries[0][0],
            notification_type=NotificationType.SHIFT_UPDATED,
            priority=NotificationPriority.NORMAL,
        )

    complete_finished_roster_entries(db)
    return {
        "success": True,
        "created": len(created),
        "skipped": skipped,
        "ids": created,
        "errors": errors,
    }


def _roster_base_query(
    db: Session,
    *,
    nurse_id: int | None = None,
    shift_id: int | None = None,
    department_id: int | None = None,
):
    q = db.query(NurseWorkforceRoster).filter(NurseWorkforceRoster.status != "cancelled")
    if nurse_id:
        q = q.filter(NurseWorkforceRoster.nurse_id == nurse_id)
    if shift_id:
        q = q.filter(NurseWorkforceRoster.shift_id == shift_id)
    if department_id:
        q = q.filter(NurseWorkforceRoster.department_id == department_id)
    return q


def _contiguous_span_overlaps(
    rows: list[NurseWorkforceRoster],
    date_from: date | None,
    date_to: date | None,
) -> bool:
    start = rows[0].roster_date
    end = rows[-1].roster_date
    window_start = date_from or start
    window_end = date_to or end
    return start <= window_end and end >= window_start


def _expand_roster_spans(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    nurse_id: int | None,
    shift_id: int | None,
    department_id: int | None,
) -> list[NurseWorkforceRoster]:
    """Include every consecutive day of an assignment that overlaps the filter."""
    window = _roster_base_query(
        db, nurse_id=nurse_id, shift_id=shift_id, department_id=department_id
    )
    if date_from:
        window = window.filter(NurseWorkforceRoster.roster_date >= date_from)
    if date_to:
        window = window.filter(NurseWorkforceRoster.roster_date <= date_to)
    keys = {
        (nurse_id, shift_id)
        for nurse_id, shift_id in window.with_entities(
            NurseWorkforceRoster.nurse_id, NurseWorkforceRoster.shift_id
        ).distinct()
    }
    if not keys:
        return []

    keyed = (
        _roster_base_query(db, nurse_id=nurse_id, shift_id=shift_id, department_id=department_id)
        .filter(
            or_(
                *[
                    and_(
                        NurseWorkforceRoster.nurse_id == nid,
                        NurseWorkforceRoster.shift_id == sid,
                    )
                    for nid, sid in keys
                ]
            )
        )
        .order_by(
            NurseWorkforceRoster.nurse_id.asc(),
            NurseWorkforceRoster.shift_id.asc(),
            NurseWorkforceRoster.roster_date.asc(),
        )
        .all()
    )
    expanded: list[NurseWorkforceRoster] = []
    current: list[NurseWorkforceRoster] = []
    current_key: tuple[int, int] | None = None
    for row in keyed:
        key = (row.nurse_id, row.shift_id)
        consecutive = (
            current
            and current_key == key
            and (row.roster_date - current[-1].roster_date).days == 1
        )
        if consecutive:
            current.append(row)
            continue
        if current and _contiguous_span_overlaps(current, date_from, date_to):
            expanded.extend(current)
        current = [row]
        current_key = key
    if current and _contiguous_span_overlaps(current, date_from, date_to):
        expanded.extend(current)
    expanded.sort(key=lambda row: (row.roster_date, row.shift_id, row.nurse_id))
    return expanded


def list_roster_service(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    nurse_id: int | None = None,
    shift_id: int | None = None,
    department_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    complete_finished_roster_entries(db)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    if date_from or date_to:
        rows = _expand_roster_spans(
            db,
            date_from=date_from,
            date_to=date_to,
            nurse_id=nurse_id,
            shift_id=shift_id,
            department_id=department_id,
        )
    else:
        rows = (
            _roster_base_query(
                db, nurse_id=nurse_id, shift_id=shift_id, department_id=department_id
            )
            .order_by(NurseWorkforceRoster.roster_date.asc(), NurseWorkforceRoster.shift_id.asc())
            .all()
        )
    total = len(rows)
    start = (page - 1) * page_size
    rows = rows[start : start + page_size]
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_roster_out(db, r) for r in rows],
    }


def _has_active_shift_beds(
    db: Session,
    *,
    nurse_id: int,
    shift_name: str | None,
    roster_date: date,
) -> bool:
    if not shift_name:
        return False
    name = shift_name.strip().lower()
    return (
        db.query(NurseShiftBedAllocation.id)
        .filter(
            NurseShiftBedAllocation.nurse_id == nurse_id,
            NurseShiftBedAllocation.is_active.is_(True),
            func.lower(NurseShiftBedAllocation.shift_name) == name,
            NurseShiftBedAllocation.shift_date <= roster_date,
            or_(
                NurseShiftBedAllocation.assigned_until.is_(None),
                NurseShiftBedAllocation.assigned_until >= roster_date,
            ),
        )
        .first()
        is not None
    )


def delete_roster_service(
    db: Session,
    roster_id: int,
    *,
    actor: User | None = None,
) -> dict:
    row = db.query(NurseWorkforceRoster).filter(NurseWorkforceRoster.id == roster_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Roster entry not found")
    if (row.status or "").strip().lower() == "completed":
        raise HTTPException(
            status_code=400,
            detail="Completed roster shifts cannot be cancelled.",
        )
    if row.roster_date < _now().date():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Past roster shifts cannot be cancelled. "
                f"{row.roster_date.isoformat()} is already in the past."
            ),
        )
    shift = (
        db.query(NurseWorkforceShift)
        .filter(NurseWorkforceShift.id == row.shift_id)
        .first()
    )
    if _has_active_shift_beds(
        db,
        nurse_id=row.nurse_id,
        shift_name=shift.name if shift else None,
        roster_date=row.roster_date,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Deactivate this nurse's bed allocations for this shift "
                "before cancelling the roster."
            ),
        )
    row.status = "cancelled"
    row.updated_at = _now()
    db.commit()
    _notify_nurse(
        db,
        nurse_id=row.nurse_id,
        title="Shift changed",
        message=f"Your roster entry on {row.roster_date} was cancelled.",
        actor=actor,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=row.id,
        priority=NotificationPriority.HIGH,
    )
    return {"success": True, "data": _roster_out(db, row)}

# =========================================================
# Dashboard
# =========================================================

def _current_shift(db: Session) -> NurseWorkforceShift | None:
    ensure_default_shifts_service(db)
    now_t = _now().time().replace(tzinfo=None)
    shifts = (
        db.query(NurseWorkforceShift)
        .filter(NurseWorkforceShift.is_active.is_(True))
        .all()
    )
    for s in shifts:
        if s.start_time <= s.end_time:
            if s.start_time <= now_t < s.end_time:
                return s
        else:
            if now_t >= s.start_time or now_t < s.end_time:
                return s
    return shifts[0] if shifts else None


def get_workforce_dashboard_service(db: Session, *, target_date: date | None = None) -> dict:
    day = target_date or _now().date()
    complete_finished_roster_entries(db)
    ensure_default_shifts_service(db)
    current = _current_shift(db)

    on_duty_ids = {
        r[0]
        for r in db.query(NurseWorkforceRoster.nurse_id)
        .filter(
            NurseWorkforceRoster.roster_date == day,
            NurseWorkforceRoster.status.in_(["scheduled", "completed"]),
        )
        .distinct()
        .all()
    }
    total_nurses = (
        db.query(func.count(User.id))
        .join(Role, Role.id == User.role_id)
        .filter(Role.name == "nurse", User.deleted_at.is_(None), User.is_active.is_(True))
        .scalar()
        or 0
    )
    off_duty = max(total_nurses - len(on_duty_ids), 0)

    alloc_beds = {
        r[0]
        for r in db.query(NurseShiftBedAllocation.bed_id)
        .join(Bed, Bed.id == NurseShiftBedAllocation.bed_id)
        .filter(
            NurseShiftBedAllocation.is_active.is_(True),
            Bed.is_active.is_(True),
        )
        .distinct()
        .all()
    }
    total_beds = (
        db.query(func.count(Bed.id)).filter(Bed.is_active.is_(True)).scalar() or 0
    )
    coverage = round((len(alloc_beds) / total_beds) * 100, 1) if total_beds else 0.0

    return {
        "success": True,
        "date": day,
        "nurses_on_duty": len(on_duty_ids),
        "nurses_off_duty": off_duty,
        "current_shift": current.name if current else None,
        "current_shift_start": current.start_time if current else None,
        "current_shift_end": current.end_time if current else None,
        "coverage_percentage": coverage,
        "beds_assigned": len(alloc_beds),
        "beds_unassigned": max(total_beds - len(alloc_beds), 0),
        "total_nurses": total_nurses,
        "total_beds": total_beds,
    }
