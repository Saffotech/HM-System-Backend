"""Nurse Workforce Management — shifts, roster, and dashboard."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
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
        pass


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


def create_shift_service(db: Session, data: NurseWorkforceShiftCreate) -> dict:
    if db.query(NurseWorkforceShift).filter(NurseWorkforceShift.name == data.name.strip()).first():
        raise HTTPException(status_code=400, detail="Shift name already exists")
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
    if data.department_id is not None:
        if not db.query(Department).filter(Department.id == data.department_id).first():
            raise HTTPException(status_code=404, detail="Department not found")

    exists = (
        db.query(NurseWorkforceRoster)
        .filter(
            NurseWorkforceRoster.nurse_id == nurse.id,
            NurseWorkforceRoster.roster_date == data.roster_date,
            NurseWorkforceRoster.shift_id == shift.id,
            NurseWorkforceRoster.status != "cancelled",
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Roster entry already exists")

    row = NurseWorkforceRoster(
        nurse_id=nurse.id,
        shift_id=shift.id,
        department_id=data.department_id,
        roster_date=data.roster_date,
        status=data.status or "scheduled",
        notes=data.notes,
        assigned_by=assigned_by,
    )
    db.add(row)
    db.commit()
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
    return {"success": True, "data": _roster_out(db, row)}


def bulk_create_roster_service(
    db: Session,
    data: NurseWorkforceRosterBulkCreate,
    *,
    assigned_by: int,
    actor: User | None = None,
) -> dict:
    shift = db.query(NurseWorkforceShift).filter(NurseWorkforceShift.id == data.shift_id).first()
    if not shift or not shift.is_active:
        raise HTTPException(status_code=400, detail="Shift not found or inactive")

    created = []
    skipped = 0
    errors = []
    for nurse_id in dict.fromkeys(data.nurse_ids):
        try:
            nurse = _require_nurse(db, nurse_id)
        except HTTPException as exc:
            errors.append(str(exc.detail))
            skipped += 1
            continue
        for roster_date in data.dates:
            exists = (
                db.query(NurseWorkforceRoster)
                .filter(
                    NurseWorkforceRoster.nurse_id == nurse.id,
                    NurseWorkforceRoster.roster_date == roster_date,
                    NurseWorkforceRoster.shift_id == shift.id,
                    NurseWorkforceRoster.status != "cancelled",
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            row = NurseWorkforceRoster(
                nurse_id=nurse.id,
                shift_id=shift.id,
                department_id=data.department_id,
                roster_date=roster_date,
                status="scheduled",
                notes=data.notes,
                assigned_by=assigned_by,
            )
            db.add(row)
            db.flush()
            created.append(row.id)
            _notify_nurse(
                db,
                nurse_id=nurse.id,
                title="Shift assigned",
                message=f"You are rostered for {shift.name} on {roster_date}.",
                actor=actor,
                reference_type=ReferenceType.SCHEDULE,
                reference_id=row.id,
            )
    db.commit()
    return {
        "success": True,
        "created": len(created),
        "skipped": skipped,
        "ids": created,
        "errors": errors,
    }


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
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    q = db.query(NurseWorkforceRoster).filter(NurseWorkforceRoster.status != "cancelled")
    if date_from:
        q = q.filter(NurseWorkforceRoster.roster_date >= date_from)
    if date_to:
        q = q.filter(NurseWorkforceRoster.roster_date <= date_to)
    if nurse_id:
        q = q.filter(NurseWorkforceRoster.nurse_id == nurse_id)
    if shift_id:
        q = q.filter(NurseWorkforceRoster.shift_id == shift_id)
    if department_id:
        q = q.filter(NurseWorkforceRoster.department_id == department_id)
    total = q.count()
    rows = (
        q.order_by(NurseWorkforceRoster.roster_date.asc(), NurseWorkforceRoster.shift_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_roster_out(db, r) for r in rows],
    }


def delete_roster_service(
    db: Session,
    roster_id: int,
    *,
    actor: User | None = None,
) -> dict:
    row = db.query(NurseWorkforceRoster).filter(NurseWorkforceRoster.id == roster_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Roster entry not found")
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
    ensure_default_shifts_service(db)
    current = _current_shift(db)

    on_duty_ids = {
        r[0]
        for r in db.query(NurseWorkforceRoster.nurse_id)
        .filter(
            NurseWorkforceRoster.roster_date == day,
            NurseWorkforceRoster.status.in_(["scheduled", "confirmed"]),
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
        .filter(
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .distinct()
        .all()
    }
    total_beds = db.query(func.count(Bed.id)).scalar() or 0
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
