"""Nurse shift bed allocation — admin foundation (Phase 2).

Responsibility assignments only. Does not modify beds/patients or nurse workflows.
One active nurse per bed per shift. The shift is taken from the nurse roster.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
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
from Models.opd_billing import Bed
from Models.role import Role
from Models.user import User
from Schemas.nurse_shift_bed_allocation_schema import (
    NurseShiftBedAllocationBulkCreate,
    NurseShiftBedAllocationCreate,
    NurseShiftBedAllocationFilter,
    NurseShiftBedAllocationUpdate,
)
from Models.nurse_workforce import NurseWorkforceRoster, NurseWorkforceShift
from Services import audit_service as audit_service_mod
from Services.notification_service import create_notification

IST = ZoneInfo("Asia/Kolkata")

DEFAULT_SHIFT_TIMES = {
    "Morning": (time(6, 0), time(14, 0)),
    "Evening": (time(14, 0), time(22, 0)),
    "Night": (time(22, 0), time(6, 0)),
}


def _now_ist() -> datetime:
    return datetime.now(IST)


def _display_name(first: str | None, last: str | None) -> str:
    return " ".join(p for p in [(first or "").strip(), (last or "").strip()] if p) or "—"


def _actor_display_name(actor: User | None) -> str:
    if not actor:
        return "Admin"
    return _display_name(actor.first_name, actor.last_name)


def _format_clock(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


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
    """Validate target user is an active nurse. Does not use department_id."""
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
        raise HTTPException(status_code=400, detail="Selected user is not an active nurse")
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
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


def _roster_shifts_for_nurse(
    db: Session,
    nurse_id: int,
    allocation_date: date,
) -> list[NurseWorkforceShift]:
    """Roster shifts for one nurse on one date, including a shift that already finished."""
    from Services.nurse_workforce_service import complete_finished_roster_entries

    # Do not commit here. Allocation create/update may already have pending changes.
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
    """Shift name and times come from the nurse roster, not the allocation form.

    A requested name must match one rostered shift. With no name, the nurse
    must have exactly one roster shift on that date.
    """
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
    """Stored shift, or the nurse's single roster shift when the row has none.

    Does not write the row. Older allocations were saved without a shift.
    """
    stored = _normalize_shift_name(row.shift_name)
    if stored:
        return stored
    if row.shift_date is None:
        return ""
    shifts = _roster_shifts_for_nurse(db, row.nurse_id, row.shift_date)
    if len(shifts) == 1:
        return (shifts[0].name or "").strip()
    return ""


def _allocation_conflict_detail(
    db: Session,
    bed: Bed,
    conflict: NurseShiftBedAllocation,
    shift_name: str,
) -> str:
    nurse = conflict.nurse if getattr(conflict, "nurse", None) is not None else None
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


def _find_active_conflict(
    db: Session,
    *,
    bed_id: int,
    shift_name: str,
    shift_date: date,
    assigned_until: date | None = None,
    exclude_id: int | None = None,
) -> NurseShiftBedAllocation | None:
    """One active nurse per bed per shift when the date ranges overlap.

    A Morning assignment does not block Evening or Night on the same bed.
    """
    expire_stale_allocations(db, commit=False)
    wanted = _normalize_shift_name(shift_name).lower()
    if not wanted or shift_date is None:
        return None

    range_end = assigned_until or date.max
    q = db.query(NurseShiftBedAllocation).filter(
        NurseShiftBedAllocation.bed_id == bed_id,
        NurseShiftBedAllocation.is_active.is_(True),
        NurseShiftBedAllocation.shift_date <= range_end,
        or_(
            NurseShiftBedAllocation.assigned_until.is_(None),
            NurseShiftBedAllocation.assigned_until >= shift_date,
        ),
    )
    if exclude_id is not None:
        q = q.filter(NurseShiftBedAllocation.id != exclude_id)

    for row in q.all():
        if _effective_shift_name(db, row).lower() == wanted:
            return row
    return None


def expire_stale_allocations(
    db: Session,
    *,
    actor_id: int | None = None,
    commit: bool = True,
) -> int:
    """Deactivate allocations whose assigned_until date has already passed (IST).

    Beds become free for reassignment. Inclusive end date: active through
    assigned_until; expired when today > assigned_until.

    ``commit=False`` keeps the expiry in the caller's transaction so a later
    conflict error does not persist an in-progress edit.
    """
    today = _now_ist().date()
    rows = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.is_active.is_(True),
            NurseShiftBedAllocation.assigned_until.isnot(None),
            NurseShiftBedAllocation.assigned_until < today,
        )
        .all()
    )
    if not rows:
        return 0

    now = _now_ist()
    for row in rows:
        row.is_active = False
        row.updated_at = now
        _record_history(
            db,
            allocation=row,
            action="deactivated",
            actor_id=actor_id,
            remarks=(
                f"Auto-expired: assigned_until {row.assigned_until.isoformat()} "
                "has passed"
            ),
        )
    if commit:
        db.commit()
    else:
        db.flush()
    return len(rows)


def _allocation_out(db: Session, row: NurseShiftBedAllocation) -> dict:
    nurse = db.query(User).filter(User.id == row.nurse_id).first()
    bed = db.query(Bed).filter(Bed.id == row.bed_id).first()
    dept = (
        db.query(Department).filter(Department.id == row.department_id).first()
        if row.department_id
        else None
    )
    assigner = (
        db.query(User).filter(User.id == row.assigned_by).first()
        if row.assigned_by
        else None
    )
    return {
        "id": row.id,
        "nurse_id": row.nurse_id,
        "nurse_name": _display_name(nurse.first_name, nurse.last_name) if nurse else None,
        "nurse_email": nurse.email if nurse else None,
        "bed_id": row.bed_id,
        "bed_number": bed.bed_number if bed else None,
        "ward_name": bed.ward_name if bed else None,
        "shift_date": row.shift_date,  # assigned_from
        "assigned_until": getattr(row, "assigned_until", None),
        "shift_name": row.shift_name or "",
        "shift_start": row.shift_start,
        "shift_end": row.shift_end,
        "department_id": row.department_id,
        "department_name": dept.name if dept else None,
        "assigned_by": row.assigned_by,
        "assigned_by_name": (
            _display_name(assigner.first_name, assigner.last_name) if assigner else None
        ),
        "notes": row.notes,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

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
    db.add(
        NurseShiftBedAllocationHistory(
            allocation_id=allocation.id,
            action=action,
            actor_id=actor_id,
            old_nurse_id=old_nurse_id,
            new_nurse_id=new_nurse_id if new_nurse_id is not None else allocation.nurse_id,
            old_bed_id=old_bed_id,
            new_bed_id=new_bed_id if new_bed_id is not None else allocation.bed_id,
            shift_date=allocation.shift_date,
            shift_name=allocation.shift_name,
            remarks=remarks,
        )
    )


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
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
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
    except Exception:
        # Never fail business flow if audit write fails; reset session for later work.
        try:
            db.rollback()
        except Exception:
            pass


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
    """Best-effort SHIFT_UPDATED notify for bed-allocation duty changes."""
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
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

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
    start, end = roster_shift.start_time, roster_shift.end_time

    if data.department_id is not None:
        _get_department(db, data.department_id)

    assigned_until = getattr(data, "assigned_until", None)
    if assigned_until is not None and assigned_until < data.shift_date:
        raise HTTPException(
            status_code=400,
            detail="Assigned until must be on or after assigned from date",
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

    dept_id = data.department_id if data.department_id is not None else bed.department_id
    row = NurseShiftBedAllocation(
        nurse_id=nurse.id,
        bed_id=bed.id,
        shift_date=data.shift_date,
        assigned_until=assigned_until,
        shift_name=shift_name,
        shift_start=start,
        shift_end=end,
        department_id=dept_id,
        assigned_by=assigned_by,
        notes=data.notes,
        is_active=True,
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
    out = _allocation_out(db, row)
    bed_label = out.get("bed_number") or f"#{out.get('bed_id')}"
    ward_name = out.get("ward_name")
    ward_part = f" ({ward_name})" if ward_name else ""
    dates = _date_range_label(out.get("shift_date"), out.get("assigned_until"))
    shift_name_label = (out.get("shift_name") or "").strip()
    if shift_name_label:
        timing = _shift_timing_label(
            shift_name_label, out.get("shift_start"), out.get("shift_end")
        )
        notify_message = (
            f"You were assigned bed {bed_label}{ward_part} for {timing}, {dates}."
        )
    else:
        notify_message = (
            f"You were assigned bed {bed_label}{ward_part} {dates}."
        )
    nurse_id = out["nurse_id"]
    allocation_id = out["id"]

    _audit_allocation(
        db,
        actor=actor,
        action="bed_allocation.create",
        allocation_id=allocation_id,
        summary=f"Created allocation #{allocation_id} for bed {bed_label}",
        details={"new": out},
        ip_address=ip_address,
    )
    _notify_nurse_shift_change(
        db,
        nurse_id=nurse_id,
        title="Shift assigned",
        message=notify_message,
        allocation_id=allocation_id,
        actor=actor,
    )
    return {"success": True, "data": out}


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
    start, end = roster_shift.start_time, roster_shift.end_time

    if data.department_id is not None:
        _get_department(db, data.department_id)

    assigned_until = getattr(data, "assigned_until", None)
    if assigned_until is not None and assigned_until < data.shift_date:
        raise HTTPException(
            status_code=400,
            detail="Assigned until must be on or after assigned from date",
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

        dept_id = (
            data.department_id if data.department_id is not None else bed.department_id
        )
        row = NurseShiftBedAllocation(
            nurse_id=nurse.id,
            bed_id=bed.id,
            shift_date=data.shift_date,
            assigned_until=assigned_until,
            shift_name=shift_name,
            shift_start=start,
            shift_end=end,
            department_id=dept_id,
            assigned_by=assigned_by,
            notes=data.notes,
            is_active=True,
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
        dates = _date_range_label(data.shift_date, assigned_until)
        bed_count = len(created_ids)
        if shift_name:
            timing = _shift_timing_label(shift_name, start, end)
            notify_message = (
                f"You were assigned {bed_count} bed(s) for {timing}, {dates}."
            )
        else:
            notify_message = f"You were assigned {bed_count} bed(s) {dates}."
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
    row = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.id == allocation_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Allocation not found")

    old_snapshot = {
        "nurse_id": row.nurse_id,
        "bed_id": row.bed_id,
        "shift_date": str(row.shift_date) if row.shift_date else None,
        "shift_name": row.shift_name,
        "is_active": row.is_active,
        "department_id": row.department_id,
        "notes": row.notes,
    }
    old_nurse_id = row.nurse_id
    old_bed_id = row.bed_id
    was_active = row.is_active
    old_shift_name = row.shift_name
    old_shift_start = row.shift_start
    old_shift_end = row.shift_end
    old_shift_date = row.shift_date
    old_assigned_until = getattr(row, "assigned_until", None)

    payload = data.model_dump(exclude_unset=True)

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

    if "is_active" in payload and payload["is_active"] is not None:
        row.is_active = payload["is_active"]

    if "assigned_until" in payload:
        row.assigned_until = payload["assigned_until"]

    # Persistent assignment: closing sets assigned_until; reopening clears it
    # unless the caller explicitly set assigned_until in this update.
    if was_active and not row.is_active:
        if getattr(row, "assigned_until", None) is None:
            row.assigned_until = _now_ist().date()
    elif (not was_active) and row.is_active and "assigned_until" not in payload:
        row.assigned_until = None

    from_date = row.shift_date
    until_date = getattr(row, "assigned_until", None)
    if from_date and until_date and until_date < from_date:
        raise HTTPException(
            status_code=400,
            detail="Assigned until must be on or after assigned from date",
        )

    nurse_changed = (
        "nurse_id" in payload
        and payload["nurse_id"] is not None
        and payload["nurse_id"] != old_nurse_id
    )
    date_changed = (
        "shift_date" in payload
        and payload["shift_date"] is not None
        and payload["shift_date"] != old_shift_date
    )
    shift_requested = "shift_name" in payload and payload["shift_name"] is not None
    reactivated = (not was_active) and row.is_active
    if row.is_active and (
        nurse_changed
        or date_changed
        or shift_requested
        or reactivated
        or not _normalize_shift_name(row.shift_name)
    ):
        roster_shift = _resolve_roster_shift(
            db,
            row.nurse_id,
            row.shift_date,
            payload.get("shift_name") if shift_requested else None,
        )
        row.shift_name = (roster_shift.name or "").strip()
        row.shift_start = roster_shift.start_time
        row.shift_end = roster_shift.end_time
    else:
        if shift_requested:
            row.shift_name = _normalize_shift_name(payload["shift_name"])
        if "shift_start" in payload:
            row.shift_start = payload["shift_start"]
        if "shift_end" in payload:
            row.shift_end = payload["shift_end"]

    if row.is_active:
        conflict = _find_active_conflict(
            db,
            bed_id=row.bed_id,
            shift_name=row.shift_name,
            shift_date=row.shift_date,
            assigned_until=getattr(row, "assigned_until", None),
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
    elif was_active and row.is_active is False:
        action = "deactivated"
    elif (not was_active) and row.is_active is True:
        action = "activated"
    elif old_nurse_id != row.nurse_id:
        action = "reassigned"
    else:
        action = "edited"

    actor_id = actor.id if actor else row.assigned_by
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
    out = _allocation_out(db, row)

    nurse_id = out["nurse_id"]
    allocation_id = out["id"]
    bed_label = out.get("bed_number") or f"#{out.get('bed_id')}"
    ward_name = out.get("ward_name")
    ward_part = f" ({ward_name})" if ward_name else ""
    new_timing = _shift_timing_label(
        out.get("shift_name"),
        out.get("shift_start"),
        out.get("shift_end"),
    )
    new_dates = _date_range_label(out.get("shift_date"), out.get("assigned_until"))
    old_timing = _shift_timing_label(old_shift_name, old_shift_start, old_shift_end)
    is_active = bool(out.get("is_active"))

    _audit_allocation(
        db,
        actor=actor,
        action=f"bed_allocation.{action}",
        allocation_id=allocation_id,
        summary=f"{action.capitalize()} allocation #{allocation_id}",
        details={"old": old_snapshot, "new": out},
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
            allocation_id=allocation_id,
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
            allocation_id=allocation_id,
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
                allocation_id=allocation_id,
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
            allocation_id=allocation_id,
            actor=actor,
        )
    else:
        # edited / shift or schedule change
        shift_changed = (
            old_shift_name != out.get("shift_name")
            or old_shift_start != out.get("shift_start")
            or old_shift_end != out.get("shift_end")
            or old_shift_date != out.get("shift_date")
            or old_assigned_until != out.get("assigned_until")
            or old_bed_id != out.get("bed_id")
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
                allocation_id=allocation_id,
                actor=actor,
            )

    return {"success": True, "data": out}


def deactivate_allocation_service(
    db: Session,
    allocation_id: int,
    *,
    actor: User | None = None,
    ip_address: str | None = None,
) -> dict:
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
    """Soft-delete: deactivate allocation (project uses is_active, not hard delete)."""
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


def _exclude_superseded_inactive_allocations(db: Session, query):
    """Hide older inactive batches for the same nurse and shift.

    Beds saved together are inserted within a few seconds of each other.
    A later save for that nurse and shift replaces the earlier one in the
    list. Stored rows are not deleted, and active rows are left as they are.
    """
    newer = aliased(NurseShiftBedAllocation)
    same_shift = func.lower(func.btrim(func.coalesce(newer.shift_name, ""))) == func.lower(
        func.btrim(func.coalesce(NurseShiftBedAllocation.shift_name, ""))
    )
    superseded = (
        db.query(newer.id)
        .filter(
            newer.nurse_id == NurseShiftBedAllocation.nurse_id,
            newer.is_active.is_(False),
            same_shift,
            newer.created_at
            > NurseShiftBedAllocation.created_at + timedelta(seconds=30),
        )
        .exists()
    )
    return query.filter(or_(NurseShiftBedAllocation.is_active.is_(True), ~superseded))


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
        search = filters.search if filters.search is not None else search
        page = filters.page
        page_size = filters.page_size

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
        query = query.filter(NurseShiftBedAllocation.shift_date == shift_date)
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
            search_filters.append(NurseShiftBedAllocation.id == int(term))
            search_filters.append(NurseShiftBedAllocation.nurse_id == int(term))
            search_filters.append(NurseShiftBedAllocation.bed_id == int(term))
            search_filters.append(NurseShiftBedAllocation.department_id == int(term))
        query = query.filter(or_(*search_filters))

    if is_active is not True:
        query = _exclude_superseded_inactive_allocations(db, query)

    total = query.count()
    rows = (
        query.order_by(
            NurseShiftBedAllocation.shift_date.desc(),
            NurseShiftBedAllocation.shift_name.asc(),
            Bed.ward_name.asc(),
            Bed.bed_number.asc(),
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
    """Map current IST time to Morning / Evening / Night (hardcoded defaults)."""
    current = now or _now_ist()
    t = current.timetz().replace(tzinfo=None) if current.tzinfo else current.time()
    for name, (start, end) in DEFAULT_SHIFT_TIMES.items():
        if start <= end:
            if start <= t < end:
                return name
        else:
            # Overnight (Night)
            if t >= start or t < end:
                return name
    return "Morning"


def _shift_window_covers(
    now_t: time,
    start: time | None,
    end: time | None,
) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_t < end
    # Overnight window (e.g. 22:00–06:00)
    return now_t >= start or now_t < end


def _allocation_shift_times(
    row: NurseShiftBedAllocation,
) -> tuple[time | None, time | None]:
    start, end = row.shift_start, row.shift_end
    if start is not None or end is not None:
        return start, end
    return DEFAULT_SHIFT_TIMES.get(row.shift_name, (None, None))


def get_active_allocations_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
) -> list[NurseShiftBedAllocation]:
    """Active bed allocations covering the target date (persistent until range ends)."""
    expire_stale_allocations(db)
    target_date = assignment_date or _now_ist().date()
    return (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.nurse_id == nurse_id,
            NurseShiftBedAllocation.is_active.is_(True),
            NurseShiftBedAllocation.shift_date <= target_date,
            or_(
                NurseShiftBedAllocation.assigned_until.is_(None),
                NurseShiftBedAllocation.assigned_until >= target_date,
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
    1. Explicit ``shift_name`` if that nurse has active allocations for it
    2. Active allocation whose start/end covers current IST time
    3. Any active allocation for the date (admin-assigned duty)
    4. Clock-based default (Morning / Evening / Night)
    """
    current = now or _now_ist()
    now_t = current.timetz().replace(tzinfo=None) if current.tzinfo else current.time()
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
            row for row in active
            if _normalize_shift_name(row.shift_name) == wanted
        ]
        if matched:
            chosen = matched
            resolved_name = wanted

    if not chosen and active and not shift_name:
        covering = [
            row
            for row in active
            if _shift_window_covers(now_t, *_allocation_shift_times(row))
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
        # Prefer admin-assigned duty over clock default when allocations exist.
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
        start, end = _allocation_shift_times(sample)
    else:
        start, end = DEFAULT_SHIFT_TIMES.get(resolved_name, (None, None))

    return {
        "assignment_date": target_date,
        "shift_name": resolved_name,
        "shift_start": start,
        "shift_end": end,
        "allocations": chosen,
    }


def get_allocated_bed_ids_for_nurse(
    db: Session,
    nurse_id: int,
    *,
    assignment_date: date | None = None,
    shift_name: str | None = None,
) -> list[int]:
    """Active allocation bed ids for a nurse (for optional dashboard filtering)."""
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
    """Occupied patient ids on beds allocated to the nurse for the shift."""
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
    """Assignment summary for logged-in nurse (additive; does not alter bed APIs)."""
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
