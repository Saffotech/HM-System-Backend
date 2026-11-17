"""Nurse shift bed allocation — admin foundation (Phase 2).

Responsibility assignments only. Does not modify beds/patients or nurse workflows.
One active nurse per bed per shift. The shift is taken from the nurse roster.

Lifecycle:
    active       - nurse currently has responsibility
    deactivated  - an administrator manually ended the responsibility
    completed    - the scheduled allocation period ended naturally

`is_active` is retained for compatibility with existing allocation and nurse
workforce code. It must stay synchronized with `status`.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.department import Department
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory
from Models.nurse_workforce import NurseWorkforceRoster, NurseWorkforceShift
from Models.opd_billing import Bed
from Models.role import Role
from Models.user import User
from Schemas.nurse_shift_bed_allocation_schema import (
    NurseShiftBedAllocationBulkCreate,
    NurseShiftBedAllocationCreate,
    NurseShiftBedAllocationFilter,
    NurseShiftBedAllocationUpdate,
)
from Services import audit_service as audit_service_mod
from Services.notification_service import create_notification

IST = ZoneInfo("Asia/Kolkata")

VALID_ALLOCATION_STATUSES = {"active", "completed", "deactivated"}

# Legacy/dashboard display fallbacks only. New allocations always snapshot the
# actual roster shift_start and shift_end values.
DEFAULT_SHIFT_TIMES = {
    "Morning": (time(6, 0), time(14, 0)),
    "Evening": (time(14, 0), time(22, 0)),
    "Night": (time(22, 0), time(6, 0)),
}


def _now_ist() -> datetime:
    return datetime.now(IST)


def _display_name(first: str | None, last: str | None) -> str:
    return " ".join(
        part
        for part in ((first or "").strip(), (last or "").strip())
        if part
    ) or "—"


def _actor_display_name(actor: User | None) -> str:
    if actor is None:
        return "System"
    return _display_name(actor.first_name, actor.last_name)


def _format_clock(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _shift_timing_label(
    shift_name: str | None,
    shift_start: time | None = None,
    shift_end: time | None = None,
) -> str:
    name = (shift_name or "Shift").strip() or "Shift"
    start = _format_clock(shift_start)
    end = _format_clock(shift_end)
    if start and end:
        return f"{name} ({start}–{end})"
    return name


def _date_range_label(from_date: date | None, until_date: date | None) -> str:
    if from_date and until_date:
        return f"{from_date.isoformat()} to {until_date.isoformat()}"
    if from_date:
        return f"from {from_date.isoformat()} (ongoing)"
    return "date TBD"


def _normalize_shift_name(name: str | None) -> str:
    return (name or "").strip()


def _is_nurse_user(db: Session, user_id: int) -> User:
    """Validate that the selected user is an active nurse."""
    user = (
        db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(
            User.id == user_id,
            User.deleted_at.is_(None),
            Role.name == "nurse",
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Selected user is not an active nurse",
        )
    if user.is_active is False:
        raise HTTPException(status_code=400, detail="Selected nurse is inactive")
    return user


def _get_bed(db: Session, bed_id: int) -> Bed:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if not bed.is_active:
        raise HTTPException(status_code=400, detail="Bed is inactive")
    return bed


def _get_department(db: Session, department_id: int) -> Department:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


def _roster_shifts_for_nurse(
    db: Session,
    nurse_id: int,
    allocation_date: date,
) -> list[NurseWorkforceShift]:
    """Return scheduled/completed roster shifts for one nurse and date."""
    from Services.nurse_workforce_service import complete_finished_roster_entries

    # Do not commit here; allocation create/update may already have pending work.
    complete_finished_roster_entries(db, commit=False)

    rows = (
        db.query(NurseWorkforceShift)
        .join(
            NurseWorkforceRoster,
            NurseWorkforceRoster.shift_id == NurseWorkforceShift.id,
        )
        .filter(
            NurseWorkforceRoster.nurse_id == nurse_id,
            NurseWorkforceRoster.roster_date == allocation_date,
            NurseWorkforceRoster.status.in_(["scheduled", "completed"]),
        )
        .all()
    )

    distinct: dict[str, NurseWorkforceShift] = {}
    for shift in rows:
        key = (shift.name or "").strip().lower()
        if key and key not in distinct:
            distinct[key] = shift
    return list(distinct.values())


def _resolve_roster_shift(
    db: Session,
    nurse_id: int,
    allocation_date: date,
    requested_name: str | None = None,
) -> NurseWorkforceShift:
    """Resolve shift name/timings from the nurse roster, never from the form."""
    shifts = _roster_shifts_for_nurse(db, nurse_id, allocation_date)
    if not shifts:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot assign bed. No valid roster entry exists "
                "for the selected nurse and date."
            ),
        )

    requested = _normalize_shift_name(requested_name).lower()
    if requested:
        for shift in shifts:
            if (shift.name or "").strip().lower() == requested:
                return shift
        names = ", ".join(shift.name for shift in shifts)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Selected nurse is rostered for {names} on "
                f"{allocation_date.isoformat()}, not {requested_name.strip()}."
            ),
        )

    if len(shifts) > 1:
        names = ", ".join(shift.name for shift in shifts)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Selected nurse has more than one roster shift on "
                f"{allocation_date.isoformat()} ({names}). "
                "Pass shift_name to choose one."
            ),
        )
    return shifts[0]


def _effective_shift_name(db: Session, row: NurseShiftBedAllocation) -> str:
    """Return stored shift name, or resolve one roster shift for legacy rows."""
    stored = _normalize_shift_name(row.shift_name)
    if stored:
        return stored
    if row.shift_date is None:
        return ""

    shifts = _roster_shifts_for_nurse(db, row.nurse_id, row.shift_date)
    if len(shifts) == 1:
        return (shifts[0].name or "").strip()
    return ""


def _allocation_shift_times(
    row: NurseShiftBedAllocation,
) -> tuple[time | None, time | None]:
    """Return stored shift snapshot, with known legacy defaults for display."""
    if row.shift_start is not None and row.shift_end is not None:
        return row.shift_start, row.shift_end

    stored_name = _normalize_shift_name(row.shift_name).lower()
    for name, times in DEFAULT_SHIFT_TIMES.items():
        if name.lower() == stored_name:
            return times
    return None, None


def _allocation_end_datetime(
    row: NurseShiftBedAllocation,
) -> datetime | None:
    """Calculate scheduled end from stored roster timings.

    Do not guess times for custom/legacy shifts when either stored time is
    missing. Such rows need correct roster timings backfilled before automatic
    completion can safely process them.
    """
    if row.assigned_until is None:
        return None

    shift_start = row.shift_start
    shift_end = row.shift_end
    if shift_start is None or shift_end is None:
        return None

    end_date = row.assigned_until
    if shift_end <= shift_start:
        # Overnight shift, e.g. 22:00 on assigned_until to 06:00 next day.
        end_date += timedelta(days=1)

    return datetime.combine(end_date, shift_end, tzinfo=IST)


def _allocation_conflict_detail(
    db: Session,
    bed: Bed,
    conflict: NurseShiftBedAllocation,
    shift_name: str,
) -> str:
    nurse = getattr(conflict, "nurse", None)
    if nurse is None:
        nurse = db.query(User).filter(User.id == conflict.nurse_id).first()
    nurse_name = (
        _display_name(nurse.first_name, nurse.last_name)
        if nurse
        else f"nurse #{conflict.nurse_id}"
    )
    label = _normalize_shift_name(shift_name) or "that shift"
    return (
        f"Bed {bed.bed_number} is already assigned to {nurse_name} for {label}. "
        "Another nurse can take this bed on a different shift. "
        "Change or deactivate this assignment to reuse the same shift."
    )


def _commit_allocation(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "This bed already has an active assignment for that shift. "
                "Choose a nurse on another shift, or deactivate the existing assignment."
            ),
        )


def _record_history(
    db: Session,
    *,
    allocation: NurseShiftBedAllocation,
    action: str,
    actor_id: int | None,
    old_nurse_id: int | None = None,
    new_nurse_id: int | None = None,
    old_bed_id: int | None = None,
    new_bed_id: int | None = None,
    remarks: str | None = None,
) -> None:
    """Append an immutable audit-history event for an allocation."""
    actor = (
        db.query(User).filter(User.id == actor_id).first()
        if actor_id is not None
        else None
    )

    if actor_id is None:
        actor_name = "System"
    elif actor is not None:
        actor_name = _display_name(actor.first_name, actor.last_name)
    else:
        actor_name = "Unknown user"

    db.add(
        NurseShiftBedAllocationHistory(
            allocation_id=allocation.id,
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            old_nurse_id=old_nurse_id,
            new_nurse_id=(
                new_nurse_id
                if new_nurse_id is not None
                else allocation.nurse_id
            ),
            old_bed_id=old_bed_id,
            new_bed_id=(
                new_bed_id
                if new_bed_id is not None
                else allocation.bed_id
            ),
            shift_date=allocation.shift_date,
            shift_name=allocation.shift_name,
            remarks=remarks,
        )
    )


def _get_latest_allocation_status_history(
    db: Session,
    allocation_id: int,
) -> NurseShiftBedAllocationHistory | None:
    """Return the latest terminal status event for an allocation."""
    return (
        db.query(NurseShiftBedAllocationHistory)
        .filter(
            NurseShiftBedAllocationHistory.allocation_id == allocation_id,
            NurseShiftBedAllocationHistory.action.in_(
                ["deactivated", "deleted", "completed"]
            ),
        )
        .order_by(
            NurseShiftBedAllocationHistory.created_at.desc(),
            NurseShiftBedAllocationHistory.id.desc(),
        )
        .first()
    )


def _allocation_out(db: Session, row: NurseShiftBedAllocation) -> dict:
    """Serialize allocation and latest status-change actor metadata."""
    nurse = db.query(User).filter(User.id == row.nurse_id).first()
    bed = db.query(Bed).filter(Bed.id == row.bed_id).first()
    department = (
        db.query(Department).filter(Department.id == row.department_id).first()
        if row.department_id
        else None
    )
    assigner = (
        db.query(User).filter(User.id == row.assigned_by).first()
        if row.assigned_by
        else None
    )

    status_history = (
        None
        if row.is_active
        else _get_latest_allocation_status_history(db, row.id)
    )

    # is_active is the compatibility source of truth for whether the row is
    # currently active. Terminal status is taken from the persisted status,
    # then history for older rows with missing/invalid status values.
    if row.is_active:
        allocation_status = "active"
    elif row.status in {"completed", "deactivated"}:
        allocation_status = row.status
    elif status_history and status_history.action == "completed":
        allocation_status = "completed"
    else:
        allocation_status = "deactivated"

    status_changed_by_name = None
    if status_history:
        status_changed_by_name = status_history.actor_name
        if not status_changed_by_name and status_history.actor:
            status_changed_by_name = _display_name(
                status_history.actor.first_name,
                status_history.actor.last_name,
            )
        if not status_changed_by_name and status_history.actor_id is None:
            status_changed_by_name = "System"

    return {
        "id": row.id,
        "nurse_id": row.nurse_id,
        "nurse_name": (
            _display_name(nurse.first_name, nurse.last_name) if nurse else None
        ),
        "nurse_email": nurse.email if nurse else None,
        "bed_id": row.bed_id,
        "bed_number": bed.bed_number if bed else None,
        "ward_name": bed.ward_name if bed else None,
        "shift_date": row.shift_date,
        "assigned_until": row.assigned_until,
        "ended_at": getattr(row, "ended_at", None),
        "shift_name": row.shift_name or "",
        "shift_start": row.shift_start,
        "shift_end": row.shift_end,
        "department_id": row.department_id,
        "department_name": department.name if department else None,
        "assigned_by": row.assigned_by,
        "assigned_by_name": (
            _display_name(assigner.first_name, assigner.last_name)
            if assigner
            else None
        ),
        "status": allocation_status,
        "status_action": status_history.action if status_history else None,
        "status_changed_by_name": status_changed_by_name,
        "status_changed_at": (
            status_history.created_at if status_history else getattr(row, "ended_at", None)
        ),
        "status_remarks": status_history.remarks if status_history else None,
        "notes": row.notes,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _json_safe(value):
    """Make values safe for JSONB audit details (dates/times/enums)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value"):
        try:
            return value.value
        except Exception:
            pass
    return str(value)


def _audit_allocation(
    db: Session,
    *,
    actor: User | None,
    action: str,
    allocation_id: int,
    summary: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write audit event without undoing the already-committed allocation."""
    try:
        audit_service_mod.log_event(
            db,
            actor=actor,
            action=action,
            resource_type="nurse_bed_allocation",
            resource_id=allocation_id,
            summary=summary,
            details=_json_safe(details or {}),
            ip_address=ip_address,
        )
        # audit_service.log_event is expected to participate in this session.
        # Commit its event separately because the allocation transaction is done.
        db.commit()
    except Exception:
        db.rollback()


def _notify_nurse_shift_change(
    db: Session,
    *,
    nurse_id: int,
    title: str,
    message: str,
    allocation_id: int,
    actor: User | None = None,
    priority: NotificationPriority = NotificationPriority.HIGH,
) -> None:
    """Best-effort SHIFT_UPDATED notification for bed-allocation changes."""
    try:
        create_notification(
            db,
            user_id=nurse_id,
            title=title,
            message=message,
            notification_type=NotificationType.SHIFT_UPDATED,
            source_module=SourceModule.ADMIN,
            reference_type=ReferenceType.SCHEDULE,
            reference_id=allocation_id,
            created_by=actor.id if actor else None,
            created_by_name=_actor_display_name(actor),
            priority=priority,
        )
        db.commit()
    except Exception:
        db.rollback()


def _notify_nurse_bulk_shift_change(
    db: Session,
    *,
    nurse_id: int,
    shift_count: int,
    start_date: date,
    end_date: date,
    allocation_id: int,
    actor: User | None = None,
) -> None:
    _notify_nurse_shift_change(
        db,
        nurse_id=nurse_id,
        title="Bulk shift roster assigned",
        message=(
            f"You have been assigned {shift_count} bed allocation(s) "
            f"for {start_date:%d-%m-%Y} to {end_date:%d-%m-%Y}."
        ),
        allocation_id=allocation_id,
        actor=actor,
        priority=NotificationPriority.NORMAL,
    )


def expire_stale_allocations(
    db: Session,
    *,
    actor_id: int | None = None,
    commit: bool = True,
) -> int:
    """Complete allocations after their scheduled shift end has passed.

    Open-ended allocations (assigned_until=None) are not auto-completed.
    Rows without stored shift timings are left untouched rather than having a
    guessed completion time. `with_for_update` helps prevent duplicate history
    events when multiple workers check the same rows concurrently on Postgres.
    """
    now = _now_ist()
    rows = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.is_active.is_(True),
            NurseShiftBedAllocation.assigned_until.isnot(None),
            NurseShiftBedAllocation.assigned_until <= now.date(),
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    completed_count = 0
    for row in rows:
        end_datetime = _allocation_end_datetime(row)
        if end_datetime is None or now < end_datetime:
            continue

        row.is_active = False
        row.status = "completed"
        row.ended_at = end_datetime
        row.updated_at = now

        _record_history(
            db,
            allocation=row,
            action="completed",
            actor_id=actor_id,
            remarks=(
                "Automatically completed after scheduled allocation "
                f"ended at {end_datetime.isoformat()}."
            ),
        )
        completed_count += 1

    if completed_count:
        if commit:
            db.commit()
        else:
            db.flush()

    return completed_count


def _find_active_conflict(
    db: Session,
    *,
    bed_id: int,
    shift_name: str,
    shift_date: date,
    assigned_until: date | None = None,
    exclude_id: int | None = None,
) -> NurseShiftBedAllocation | None:
    """Find an overlapping active assignment for the same bed and shift."""
    expire_stale_allocations(db, commit=False)

    wanted = _normalize_shift_name(shift_name).lower()
    if not wanted:
        return None

    range_end = assigned_until or date.max
    query = db.query(NurseShiftBedAllocation).filter(
        NurseShiftBedAllocation.bed_id == bed_id,
        NurseShiftBedAllocation.is_active.is_(True),
        NurseShiftBedAllocation.shift_date <= range_end,
        or_(
            NurseShiftBedAllocation.assigned_until.is_(None),
            NurseShiftBedAllocation.assigned_until >= shift_date,
        ),
    )
    if exclude_id is not None:
        query = query.filter(NurseShiftBedAllocation.id != exclude_id)

    for row in query.all():
        if _effective_shift_name(db, row).lower() == wanted:
            return row
    return None


def _validate_allocation_dates(
    shift_date: date,
    assigned_until: date | None,
) -> None:
    if assigned_until is not None and assigned_until < shift_date:
        raise HTTPException(
            status_code=400,
            detail="Assigned until must be on or after assigned from date",
        )


def _ensure_reactivation_is_valid(row: NurseShiftBedAllocation) -> None:
    """Do not reactivate a completed or already-expired scheduled allocation."""
    if row.status == "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                "A completed allocation cannot be reactivated. "
                "Create a new allocation for the new responsibility period."
            ),
        )

    if row.assigned_until is None:
        return

    now = _now_ist()
    end_datetime = _allocation_end_datetime(row)

    if end_datetime is None:
        if row.assigned_until <= now.date():
            raise HTTPException(
                status_code=409,
                detail=(
                    "This allocation's scheduled period may already have ended, "
                    "but its shift timings are unavailable. Backfill the original "
                    "roster timings or create a new allocation."
                ),
            )
        return

    if now >= end_datetime:
        raise HTTPException(
            status_code=409,
            detail=(
                "The scheduled allocation period has already ended. "
                "Create a new allocation instead of reactivating this one."
            ),
        )


def create_allocation_service(
    db: Session,
    data: NurseShiftBedAllocationCreate,
    assigned_by: int,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
) -> dict:
    nurse = _is_nurse_user(db, data.nurse_id)
    bed = _get_bed(db, data.bed_id)
    roster_shift = _resolve_roster_shift(
        db,
        nurse.id,
        data.shift_date,
        getattr(data, "shift_name", None),
    )
    shift_name = (roster_shift.name or "").strip()
    shift_start = roster_shift.start_time
    shift_end = roster_shift.end_time

    if data.department_id is not None:
        _get_department(db, data.department_id)

    assigned_until = getattr(data, "assigned_until", None)
    _validate_allocation_dates(data.shift_date, assigned_until)

    row_end = None
    if assigned_until is not None and shift_start is not None and shift_end is not None:
        end_date = assigned_until + (
            timedelta(days=1) if shift_end <= shift_start else timedelta(days=0)
        )
        row_end = datetime.combine(end_date, shift_end, tzinfo=IST)
        if _now_ist() >= row_end:
            raise HTTPException(
                status_code=400,
                detail="The scheduled allocation period has already ended.",
            )

    conflict = _find_active_conflict(
        db,
        bed_id=bed.id,
        shift_name=shift_name,
        shift_date=data.shift_date,
        assigned_until=assigned_until,
    )
    if conflict:
        raise HTTPException(
            status_code=400,
            detail=_allocation_conflict_detail(db, bed, conflict, shift_name),
        )

    department_id = (
        data.department_id if data.department_id is not None else bed.department_id
    )
    row = NurseShiftBedAllocation(
        nurse_id=nurse.id,
        bed_id=bed.id,
        shift_date=data.shift_date,
        assigned_until=assigned_until,
        ended_at=None,
        shift_name=shift_name,
        shift_start=shift_start,
        shift_end=shift_end,
        department_id=department_id,
        assigned_by=assigned_by,
        notes=data.notes,
        is_active=True,
        status="active",
    )
    db.add(row)
    db.flush()

    _record_history(
        db,
        allocation=row,
        action="created",
        actor_id=assigned_by,
        new_nurse_id=row.nurse_id,
        new_bed_id=row.bed_id,
        remarks=data.notes,
    )
    _commit_allocation(db)
    db.refresh(row)

    output = _allocation_out(db, row)
    bed_label = output.get("bed_number") or f"#{output.get('bed_id')}"
    ward_part = f" ({output['ward_name']})" if output.get("ward_name") else ""
    dates = _date_range_label(output.get("shift_date"), output.get("assigned_until"))
    timing = _shift_timing_label(
        output.get("shift_name"),
        output.get("shift_start"),
        output.get("shift_end"),
    )
    notify_message = (
        f"You were assigned bed {bed_label}{ward_part} for {timing}, {dates}."
    )

    _audit_allocation(
        db,
        actor=actor,
        action="bed_allocation.create",
        allocation_id=output["id"],
        summary=f"Created allocation #{output['id']} for bed {bed_label}",
        details={"new": output},
        ip_address=ip_address,
    )
    _notify_nurse_shift_change(
        db,
        nurse_id=output["nurse_id"],
        title="Shift assigned",
        message=notify_message,
        allocation_id=output["id"],
        actor=actor,
    )
    return {"success": True, "data": output}


def bulk_create_allocations_service(
    db: Session,
    data: NurseShiftBedAllocationBulkCreate,
    assigned_by: int,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
) -> dict:
    nurse = _is_nurse_user(db, data.nurse_id)
    roster_shift = _resolve_roster_shift(
        db,
        nurse.id,
        data.shift_date,
        getattr(data, "shift_name", None),
    )
    shift_name = (roster_shift.name or "").strip()
    shift_start = roster_shift.start_time
    shift_end = roster_shift.end_time

    if data.department_id is not None:
        _get_department(db, data.department_id)

    assigned_until = getattr(data, "assigned_until", None)
    _validate_allocation_dates(data.shift_date, assigned_until)

    if assigned_until is not None and shift_start is not None and shift_end is not None:
        end_date = assigned_until + (
            timedelta(days=1) if shift_end <= shift_start else timedelta(days=0)
        )
        end_datetime = datetime.combine(end_date, shift_end, tzinfo=IST)
        if _now_ist() >= end_datetime:
            raise HTTPException(
                status_code=400,
                detail="The scheduled allocation period has already ended.",
            )

    created_items: list[dict] = []
    created_ids: list[int] = []
    errors: list[str] = []
    skipped = 0
    unique_bed_ids = list(dict.fromkeys(data.bed_ids))

    for bed_id in unique_bed_ids:
        try:
            bed = _get_bed(db, bed_id)
        except HTTPException as exc:
            errors.append(str(exc.detail))
            skipped += 1
            continue

        conflict = _find_active_conflict(
            db,
            bed_id=bed.id,
            shift_name=shift_name,
            shift_date=data.shift_date,
            assigned_until=assigned_until,
        )
        if conflict:
            errors.append(_allocation_conflict_detail(db, bed, conflict, shift_name))
            skipped += 1
            continue

        department_id = (
            data.department_id if data.department_id is not None else bed.department_id
        )
        row = NurseShiftBedAllocation(
            nurse_id=nurse.id,
            bed_id=bed.id,
            shift_date=data.shift_date,
            assigned_until=assigned_until,
            ended_at=None,
            shift_name=shift_name,
            shift_start=shift_start,
            shift_end=shift_end,
            department_id=department_id,
            assigned_by=assigned_by,
            notes=data.notes,
            is_active=True,
            status="active",
        )
        db.add(row)
        db.flush()

        _record_history(
            db,
            allocation=row,
            action="created",
            actor_id=assigned_by,
            new_nurse_id=row.nurse_id,
            new_bed_id=row.bed_id,
            remarks=data.notes,
        )
        created_ids.append(row.id)
        created_items.append(_allocation_out(db, row))

    _commit_allocation(db)

    if created_ids:
        _audit_allocation(
            db,
            actor=actor,
            action="bed_allocation.bulk_create",
            allocation_id=created_ids[0],
            summary=f"Bulk created {len(created_ids)} bed allocation(s)",
            details={"created_ids": created_ids, "skipped": skipped},
            ip_address=ip_address,
        )
        _notify_nurse_bulk_shift_change(
            db,
            nurse_id=nurse.id,
            shift_count=len(created_ids),
            start_date=data.shift_date,
            end_date=assigned_until or data.shift_date,
            allocation_id=created_ids[0],
            actor=actor,
        )

    return {
        "success": True,
        "created": len(created_items),
        "skipped": skipped,
        "items": created_items,
        "errors": errors,
    }


def update_allocation_service(
    db: Session,
    allocation_id: int,
    data: NurseShiftBedAllocationUpdate,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
    history_action: str | None = None,
    remarks: str | None = None,
) -> dict:
    # Persist natural completion before processing a user edit/deactivation.
    # This prevents a late manual click from misclassifying a finished shift.
    expire_stale_allocations(db, commit=True)

    row = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.id == allocation_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Allocation not found")

    old_snapshot = {
        "nurse_id": row.nurse_id,
        "bed_id": row.bed_id,
        "shift_date": row.shift_date,
        "assigned_until": row.assigned_until,
        "ended_at": getattr(row, "ended_at", None),
        "shift_name": row.shift_name,
        "shift_start": row.shift_start,
        "shift_end": row.shift_end,
        "is_active": row.is_active,
        "status": row.status,
        "department_id": row.department_id,
        "notes": row.notes,
    }

    old_nurse_id = row.nurse_id
    old_bed_id = row.bed_id
    was_active = bool(row.is_active)
    old_shift_name = row.shift_name
    old_shift_start = row.shift_start
    old_shift_end = row.shift_end
    old_shift_date = row.shift_date
    old_assigned_until = row.assigned_until
    old_ended_at = getattr(row, "ended_at", None)

    payload = data.model_dump(exclude_unset=True)

    # Completed allocations are historical records. Do not rewrite their
    # nurse/bed/shift/date identity; create a new allocation instead.
    immutable_fields = {
        "nurse_id",
        "bed_id",
        "shift_date",
        "assigned_until",
        "shift_name",
        "shift_start",
        "shift_end",
    }
    if row.status == "completed" and immutable_fields.intersection(payload):
        raise HTTPException(
            status_code=409,
            detail="Completed allocations are historical records and cannot be reassigned or rescheduled.",
        )

    if "nurse_id" in payload and payload["nurse_id"] is not None:
        _is_nurse_user(db, payload["nurse_id"])
        row.nurse_id = payload["nurse_id"]

    if "bed_id" in payload and payload["bed_id"] is not None:
        _get_bed(db, payload["bed_id"])
        row.bed_id = payload["bed_id"]

    if "shift_date" in payload and payload["shift_date"] is not None:
        row.shift_date = payload["shift_date"]

    if "department_id" in payload:
        if payload["department_id"] is not None:
            _get_department(db, payload["department_id"])
        row.department_id = payload["department_id"]

    if "notes" in payload:
        row.notes = payload["notes"]

    if "assigned_until" in payload:
        row.assigned_until = payload["assigned_until"]

    requested_active = payload.get("is_active")
    reactivated = False
    if requested_active is not None:
        requested_active = bool(requested_active)
        if requested_active != was_active:
            if requested_active:
                _ensure_reactivation_is_valid(row)
                row.is_active = True
                row.status = "active"
                row.ended_at = None
                reactivated = True
            else:
                row.is_active = False
                row.status = "deactivated"
                row.ended_at = _now_ist()

    _validate_allocation_dates(row.shift_date, row.assigned_until)

    nurse_changed = row.nurse_id != old_nurse_id
    date_changed = row.shift_date != old_shift_date
    shift_name_requested = (
        "shift_name" in payload and payload["shift_name"] is not None
    )
    shift_timing_requested = (
        "shift_start" in payload or "shift_end" in payload
    )

    if row.is_active and (
        nurse_changed
        or date_changed
        or shift_name_requested
        or shift_timing_requested
        or reactivated
        or not _normalize_shift_name(row.shift_name)
    ):
        requested_shift_name = (
            payload.get("shift_name")
            if shift_name_requested
            else row.shift_name
        )
        roster_shift = _resolve_roster_shift(
            db,
            row.nurse_id,
            row.shift_date,
            requested_shift_name,
        )
        row.shift_name = (roster_shift.name or "").strip()
        row.shift_start = roster_shift.start_time
        row.shift_end = roster_shift.end_time
    elif not row.is_active:
        # Keep the original roster snapshot on inactive records. Editing the
        # original shift timings would falsify their historical assignment.
        if shift_name_requested or shift_timing_requested:
            raise HTTPException(
                status_code=409,
                detail="Inactive allocation shift details cannot be changed. Create a new allocation instead.",
            )

    if reactivated:
        _ensure_reactivation_is_valid(row)

    if row.is_active:
        # Do not allow an edit to create an already-expired active allocation.
        scheduled_end = _allocation_end_datetime(row)
        if scheduled_end is not None and _now_ist() >= scheduled_end:
            raise HTTPException(
                status_code=400,
                detail="The scheduled allocation period has already ended.",
            )

        conflict = _find_active_conflict(
            db,
            bed_id=row.bed_id,
            shift_name=row.shift_name,
            shift_date=row.shift_date,
            assigned_until=row.assigned_until,
            exclude_id=row.id,
        )
        if conflict:
            bed = _get_bed(db, row.bed_id)
            raise HTTPException(
                status_code=400,
                detail=_allocation_conflict_detail(db, bed, conflict, row.shift_name),
            )

    if history_action:
        action = history_action
    elif was_active and not row.is_active:
        action = "deactivated"
    elif not was_active and row.is_active:
        action = "activated"
    elif nurse_changed:
        action = "reassigned"
    else:
        action = "edited"

    changed = (
        old_nurse_id != row.nurse_id
        or old_bed_id != row.bed_id
        or old_shift_date != row.shift_date
        or old_assigned_until != row.assigned_until
        or old_shift_name != row.shift_name
        or old_shift_start != row.shift_start
        or old_shift_end != row.shift_end
        or old_snapshot["department_id"] != row.department_id
        or old_snapshot["notes"] != row.notes
        or was_active != bool(row.is_active)
        or old_ended_at != getattr(row, "ended_at", None)
    )

    # Avoid duplicate history/notifications for repeated no-op requests.
    if not changed and history_action != "deleted":
        return {"success": True, "data": _allocation_out(db, row)}

    actor_id = actor.id if actor is not None else None
    _record_history(
        db,
        allocation=row,
        action=action,
        actor_id=actor_id,
        old_nurse_id=old_nurse_id,
        new_nurse_id=row.nurse_id,
        old_bed_id=old_bed_id,
        new_bed_id=row.bed_id,
        remarks=remarks or row.notes,
    )

    row.updated_at = _now_ist()
    _commit_allocation(db)
    db.refresh(row)
    output = _allocation_out(db, row)

    nurse_id = output["nurse_id"]
    bed_label = output.get("bed_number") or f"#{output.get('bed_id')}"
    ward_part = f" ({output['ward_name']})" if output.get("ward_name") else ""
    new_timing = _shift_timing_label(
        output.get("shift_name"),
        output.get("shift_start"),
        output.get("shift_end"),
    )
    new_dates = _date_range_label(output.get("shift_date"), output.get("assigned_until"))
    old_timing = _shift_timing_label(old_shift_name, old_shift_start, old_shift_end)
    is_active = bool(output.get("is_active"))

    _audit_allocation(
        db,
        actor=actor,
        action=f"bed_allocation.{action}",
        allocation_id=output["id"],
        summary=f"{action.capitalize()} allocation #{output['id']}",
        details={"old": old_snapshot, "new": output},
        ip_address=ip_address,
    )

    if action in ("deactivated", "deleted"):
        _notify_nurse_shift_change(
            db,
            nurse_id=nurse_id,
            title="Shift changed",
            message=(
                f"Your assignment for bed {bed_label}{ward_part} "
                f"({old_timing}) was {action}."
            ),
            allocation_id=output["id"],
            actor=actor,
            priority=NotificationPriority.HIGH,
        )
    elif action == "reassigned" and old_nurse_id != nurse_id:
        _notify_nurse_shift_change(
            db,
            nurse_id=old_nurse_id,
            title="Shift changed",
            message=(
                f"Bed {bed_label}{ward_part} was reassigned away from you "
                f"({old_timing})."
            ),
            allocation_id=output["id"],
            actor=actor,
            priority=NotificationPriority.HIGH,
        )
        if is_active:
            _notify_nurse_shift_change(
                db,
                nurse_id=nurse_id,
                title="Shift assigned",
                message=(
                    f"You were assigned bed {bed_label}{ward_part} "
                    f"for {new_timing}, {new_dates}."
                ),
                allocation_id=output["id"],
                actor=actor,
            )
    elif action == "activated":
        _notify_nurse_shift_change(
            db,
            nurse_id=nurse_id,
            title="Shift assigned",
            message=(
                f"Your assignment for bed {bed_label}{ward_part} "
                f"was reactivated for {new_timing}, {new_dates}."
            ),
            allocation_id=output["id"],
            actor=actor,
        )
    elif action in ("edited", "created"):
        shift_changed = (
            old_shift_name != output.get("shift_name")
            or old_shift_start != output.get("shift_start")
            or old_shift_end != output.get("shift_end")
            or old_shift_date != output.get("shift_date")
            or old_assigned_until != output.get("assigned_until")
            or old_bed_id != output.get("bed_id")
        )
        if shift_changed or action == "edited":
            _notify_nurse_shift_change(
                db,
                nurse_id=nurse_id,
                title="Shift changed",
                message=(
                    f"Your bed assignment was updated: bed {bed_label}{ward_part}, "
                    f"{new_timing}, {new_dates}."
                ),
                allocation_id=output["id"],
                actor=actor,
            )

    return {"success": True, "data": output}


def deactivate_allocation_service(
    db: Session,
    allocation_id: int,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
) -> dict:
    # First settle any naturally completed allocation. This ensures a late
    # manual click cannot overwrite completed with deactivated.
    expire_stale_allocations(db, commit=True)

    row = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.id == allocation_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Allocation not found")
    if not row.is_active:
        raise HTTPException(
            status_code=409,
            detail=f"Allocation is already {row.status or 'inactive'}.",
        )

    return update_allocation_service(
        db,
        allocation_id,
        NurseShiftBedAllocationUpdate(is_active=False),
        actor=actor,
        ip_address=ip_address,
        history_action="deactivated",
    )


def delete_allocation_service(
    db: Session,
    allocation_id: int,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
) -> dict:
    """Soft-delete an allocation by deactivating it; never hard-delete history."""
    expire_stale_allocations(db, commit=True)

    row = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.id == allocation_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Allocation not found")
    if not row.is_active:
        raise HTTPException(
            status_code=409,
            detail=f"Allocation is already {row.status or 'inactive'}.",
        )

    return update_allocation_service(
        db,
        allocation_id,
        NurseShiftBedAllocationUpdate(is_active=False),
        actor=actor,
        ip_address=ip_address,
        history_action="deleted",
        remarks="Soft-deleted (deactivated)",
    )


def get_allocation_service(db: Session, allocation_id: int) -> dict:
    expire_stale_allocations(db)
    row = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.id == allocation_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Allocation not found")
    return {"success": True, "data": _allocation_out(db, row)}


def list_allocations_service(
    db: Session,
    filters: NurseShiftBedAllocationFilter | None = None,
    *,
    nurse_id: int | None = None,
    bed_id: int | None = None,
    shift_date: date | None = None,
    shift_name: str | None = None,
    department_id: int | None = None,
    ward_name: str | None = None,
    is_active: bool | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    expire_stale_allocations(db)

    if filters is not None:
        nurse_id = filters.nurse_id if filters.nurse_id is not None else nurse_id
        bed_id = filters.bed_id if filters.bed_id is not None else bed_id
        shift_date = filters.shift_date if filters.shift_date is not None else shift_date
        shift_name = filters.shift_name if filters.shift_name is not None else shift_name
        department_id = (
            filters.department_id if filters.department_id is not None else department_id
        )
        ward_name = filters.ward_name if filters.ward_name is not None else ward_name
        is_active = filters.is_active if filters.is_active is not None else is_active
        filter_status = getattr(filters, "status", None)
        if filter_status is not None:
            status = filter_status
        search = filters.search if filters.search is not None else search
        page = filters.page
        page_size = filters.page_size

    if status is not None:
        status = status.strip().lower()
        if status not in VALID_ALLOCATION_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid allocation status. Allowed: "
                    "active, completed, deactivated."
                ),
            )

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    NurseUser = aliased(User)
    query = (
        db.query(NurseShiftBedAllocation)
        .join(Bed, Bed.id == NurseShiftBedAllocation.bed_id)
        .join(NurseUser, NurseUser.id == NurseShiftBedAllocation.nurse_id)
        .outerjoin(Department, Department.id == NurseShiftBedAllocation.department_id)
    )

    if nurse_id is not None:
        query = query.filter(NurseShiftBedAllocation.nurse_id == nurse_id)
    if bed_id is not None:
        query = query.filter(NurseShiftBedAllocation.bed_id == bed_id)

    if shift_date is not None:
        selected_day_start = datetime.combine(shift_date, time.min, tzinfo=IST)
        is_overnight = and_(
            NurseShiftBedAllocation.shift_start.isnot(None),
            NurseShiftBedAllocation.shift_end.isnot(None),
            NurseShiftBedAllocation.shift_end <= NurseShiftBedAllocation.shift_start,
        )
        scheduled_period_covers_day = or_(
            NurseShiftBedAllocation.assigned_until.is_(None),
            NurseShiftBedAllocation.assigned_until >= shift_date,
            and_(
                NurseShiftBedAllocation.assigned_until == shift_date - timedelta(days=1),
                is_overnight,
            ),
        )
        query = query.filter(
            NurseShiftBedAllocation.shift_date <= shift_date,
            or_(
                # Actual end timestamp: include every calendar date up to the
                # actual end, including the next date for an overnight shift.
                and_(
                    NurseShiftBedAllocation.ended_at.isnot(None),
                    NurseShiftBedAllocation.ended_at >= selected_day_start,
                ),
                # No actual end timestamp: use the scheduled date range.
                and_(
                    NurseShiftBedAllocation.ended_at.is_(None),
                    scheduled_period_covers_day,
                ),
            ),
        )

    if shift_name:
        query = query.filter(
            NurseShiftBedAllocation.shift_name.ilike(f"%{shift_name.strip()}%")
        )
    if department_id is not None:
        query = query.filter(NurseShiftBedAllocation.department_id == department_id)
    if ward_name:
        query = query.filter(Bed.ward_name.ilike(f"%{ward_name.strip()}%"))
    if is_active is not None:
        query = query.filter(NurseShiftBedAllocation.is_active.is_(is_active))
    if status is not None:
        query = query.filter(NurseShiftBedAllocation.status == status)

    if search:
        term = search.strip()
        search_filters = [
            Bed.bed_number.ilike(f"%{term}%"),
            Bed.ward_name.ilike(f"%{term}%"),
            NurseUser.first_name.ilike(f"%{term}%"),
            NurseUser.last_name.ilike(f"%{term}%"),
            NurseUser.email.ilike(f"%{term}%"),
            NurseShiftBedAllocation.shift_name.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            numeric_term = int(term)
            search_filters.extend(
                [
                    NurseShiftBedAllocation.id == numeric_term,
                    NurseShiftBedAllocation.nurse_id == numeric_term,
                    NurseShiftBedAllocation.bed_id == numeric_term,
                    NurseShiftBedAllocation.department_id == numeric_term,
                ]
            )
        query = query.filter(or_(*search_filters))

    total = query.count()
    rows = (
        query.order_by(
            NurseShiftBedAllocation.shift_date.desc(),
            NurseShiftBedAllocation.shift_name.asc(),
            Bed.ward_name.asc(),
            Bed.bed_number.asc(),
            NurseShiftBedAllocation.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_allocation_out(db, row) for row in rows],
    }


# ==========================================================
# Phase 4 helpers — used by nurse dashboard optional filter
# ==========================================================


def resolve_current_shift_name(now: datetime | None = None) -> str:
    """Map current IST time to legacy Morning/Evening/Night defaults."""
    current = now or _now_ist()
    current_time = (
        current.timetz().replace(tzinfo=None) if current.tzinfo else current.time()
    )

    for name, (start, end) in DEFAULT_SHIFT_TIMES.items():
        if start <= end:
            if start <= current_time < end:
                return name
        elif current_time >= start or current_time < end:
            return name
    return "Morning"


def _shift_window_covers(
    now_time: time,
    start: time | None,
    end: time | None,
) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_time < end
    return now_time >= start or now_time < end


def get_active_allocations_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
) -> list[NurseShiftBedAllocation]:
    """Return active allocations covering the requested date.

    An overnight allocation assigned_until the previous calendar date still
    covers the following date until its stored shift end. Expiry is processed
    first, so allocations past their actual end time are deactivated.
    """
    expire_stale_allocations(db)
    target_date = assignment_date or _now_ist().date()

    overnight_previous_day = and_(
        NurseShiftBedAllocation.assigned_until == target_date - timedelta(days=1),
        NurseShiftBedAllocation.shift_start.isnot(None),
        NurseShiftBedAllocation.shift_end.isnot(None),
        NurseShiftBedAllocation.shift_end <= NurseShiftBedAllocation.shift_start,
    )

    return (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.nurse_id == nurse_id,
            NurseShiftBedAllocation.is_active.is_(True),
            NurseShiftBedAllocation.shift_date <= target_date,
            or_(
                NurseShiftBedAllocation.assigned_until.is_(None),
                NurseShiftBedAllocation.assigned_until >= target_date,
                overnight_previous_day,
            ),
        )
        .order_by(NurseShiftBedAllocation.id.asc())
        .all()
    )


def resolve_duty_shift_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
    shift_name: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Resolve the nurse's on-duty shift from active bed allocations.

    Priority:
    1. Explicit shift_name if that nurse has active allocations for it.
    2. Active allocation whose stored start/end covers the current IST time.
    3. Any active allocation for the date (admin-assigned duty).
    4. Legacy clock-based default.
    """
    current = now or _now_ist()
    now_time = (
        current.timetz().replace(tzinfo=None) if current.tzinfo else current.time()
    )
    target_date = assignment_date or current.date()

    active = get_active_allocations_for_nurse(
        db,
        nurse_id,
        assignment_date=target_date,
    )

    chosen: list[NurseShiftBedAllocation] = []
    resolved_name: str | None = None

    if shift_name:
        wanted = _normalize_shift_name(shift_name)
        matched = [
            row
            for row in active
            if _normalize_shift_name(row.shift_name) == wanted
        ]
        if matched:
            chosen = matched
            resolved_name = wanted

    if not chosen and active and not shift_name:
        covering = [
            row
            for row in active
            if _shift_window_covers(
                now_time,
                *_allocation_shift_times(row),
            )
        ]
        if covering:
            resolved_name = covering[0].shift_name
            chosen = [
                row
                for row in active
                if _normalize_shift_name(row.shift_name)
                == _normalize_shift_name(resolved_name)
            ]

    if not chosen and active and not shift_name:
        resolved_name = active[0].shift_name
        chosen = [
            row
            for row in active
            if _normalize_shift_name(row.shift_name)
            == _normalize_shift_name(resolved_name)
        ]

    if resolved_name is None:
        resolved_name = (
            _normalize_shift_name(shift_name)
            if shift_name
            else resolve_current_shift_name(current)
        )

    sample = chosen[0] if chosen else None
    if sample:
        shift_start, shift_end = _allocation_shift_times(sample)
    else:
        shift_start, shift_end = DEFAULT_SHIFT_TIMES.get(
            resolved_name,
            (None, None),
        )

    return {
        "assignment_date": target_date,
        "shift_name": resolved_name,
        "shift_start": shift_start,
        "shift_end": shift_end,
        "allocations": chosen,
    }


def get_allocated_bed_ids_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
    shift_name: str | None = None,
) -> list[int]:
    """Return allocated bed IDs for the nurse's resolved duty shift."""
    duty = resolve_duty_shift_for_nurse(
        db,
        nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    return list({row.bed_id for row in duty["allocations"]})


def get_allocated_patient_ids_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
    shift_name: str | None = None,
) -> list[int]:
    """Return occupied patient IDs on beds allocated to the nurse for the shift."""
    bed_ids = get_allocated_bed_ids_for_nurse(
        db,
        nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    if not bed_ids:
        return []

    rows = (
        db.query(Bed.patient_id)
        .filter(
            Bed.id.in_(bed_ids),
            Bed.status == "occupied",
            Bed.is_active.is_(True),
            Bed.patient_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def get_nurse_allocation_summary_service(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
    shift_name: str | None = None,
) -> dict:
    """Return assignment counts for the logged-in nurse; does not modify bed APIs."""
    duty = resolve_duty_shift_for_nurse(
        db,
        nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    allocations = duty["allocations"]
    bed_ids = list({row.bed_id for row in allocations})
    assigned = len(bed_ids)
    occupied = 0

    if bed_ids:
        occupied = (
            db.query(Bed)
            .filter(
                Bed.id.in_(bed_ids),
                Bed.status == "occupied",
                Bed.is_active.is_(True),
                Bed.patient_id.isnot(None),
            )
            .count()
        )

    return {
        "success": True,
        "has_allocations": assigned > 0,
        "assignment_date": duty["assignment_date"],
        "shift_name": duty["shift_name"],
        "shift_start": duty["shift_start"],
        "shift_end": duty["shift_end"],
        "assigned_bed_count": assigned,
        "occupied_count": occupied,
        "vacant_count": max(assigned - occupied, 0),
        "allocated_bed_ids": bed_ids,
    }
