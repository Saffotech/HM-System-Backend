"""Phase 6 — allocation history, dashboard, reports, conflicts, workload analytics.

Additive read APIs only. Does not change allocation CRUD contracts.
"""
from __future__ import annotations

from datetime import date, time
from collections import defaultdict

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from Models.department import Department
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory
from Models.opd_billing import Bed
from Models.role import Role
from Models.user import User
from Services.nurse_shift_bed_allocation_service import (
    DEFAULT_SHIFT_TIMES,
    _display_name,
    _now_ist,
)


def _bed_label(bed: Bed | None) -> str | None:
    if not bed:
        return None
    ward = (bed.ward_name or "").strip()
    number = (bed.bed_number or "").strip()
    if ward and number:
        return f"{ward} / {number}"
    return number or ward or f"Bed #{bed.id}"


def _user_label(user: User | None) -> str | None:
    if not user:
        return None
    return _display_name(user.first_name, user.last_name)


def _history_out(row: NurseShiftBedAllocationHistory) -> dict:
    return {
        "id": row.id,
        "allocation_id": row.allocation_id,
        "action": row.action,
        "actor_id": row.actor_id,
        "actor_name": _user_label(row.actor) if getattr(row, "actor", None) else None,
        "old_nurse_id": row.old_nurse_id,
        "old_nurse_name": _user_label(row.old_nurse) if getattr(row, "old_nurse", None) else None,
        "new_nurse_id": row.new_nurse_id,
        "new_nurse_name": _user_label(row.new_nurse) if getattr(row, "new_nurse", None) else None,
        "old_bed_id": row.old_bed_id,
        "old_bed_label": _bed_label(row.old_bed) if getattr(row, "old_bed", None) else None,
        "new_bed_id": row.new_bed_id,
        "new_bed_label": _bed_label(row.new_bed) if getattr(row, "new_bed", None) else None,
        "shift_date": row.shift_date,
        "shift_name": row.shift_name,
        "remarks": row.remarks,
        "created_at": row.created_at,
    }


def list_allocation_history_service(
    db: Session,
    *,
    allocation_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    shift_date: date | None = None,
    shift_name: str | None = None,
    nurse_id: int | None = None,
    bed_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    Actor = aliased(User)
    OldNurse = aliased(User)
    NewNurse = aliased(User)
    OldBed = aliased(Bed)
    NewBed = aliased(Bed)

    query = (
        db.query(NurseShiftBedAllocationHistory)
        .outerjoin(Actor, Actor.id == NurseShiftBedAllocationHistory.actor_id)
        .outerjoin(OldNurse, OldNurse.id == NurseShiftBedAllocationHistory.old_nurse_id)
        .outerjoin(NewNurse, NewNurse.id == NurseShiftBedAllocationHistory.new_nurse_id)
        .outerjoin(OldBed, OldBed.id == NurseShiftBedAllocationHistory.old_bed_id)
        .outerjoin(NewBed, NewBed.id == NurseShiftBedAllocationHistory.new_bed_id)
    )

    if allocation_id is not None:
        query = query.filter(NurseShiftBedAllocationHistory.allocation_id == allocation_id)
    if actor_id is not None:
        query = query.filter(NurseShiftBedAllocationHistory.actor_id == actor_id)
    if action:
        query = query.filter(NurseShiftBedAllocationHistory.action == action.strip().lower())
    if shift_date is not None:
        query = query.filter(NurseShiftBedAllocationHistory.shift_date == shift_date)
    if shift_name:
        query = query.filter(
            NurseShiftBedAllocationHistory.shift_name.ilike(f"%{shift_name.strip()}%")
        )
    if nurse_id is not None:
        query = query.filter(
            or_(
                NurseShiftBedAllocationHistory.old_nurse_id == nurse_id,
                NurseShiftBedAllocationHistory.new_nurse_id == nurse_id,
            )
        )
    if bed_id is not None:
        query = query.filter(
            or_(
                NurseShiftBedAllocationHistory.old_bed_id == bed_id,
                NurseShiftBedAllocationHistory.new_bed_id == bed_id,
            )
        )
    if search:
        term = search.strip()
        filters = [
            Actor.first_name.ilike(f"%{term}%"),
            Actor.last_name.ilike(f"%{term}%"),
            OldNurse.first_name.ilike(f"%{term}%"),
            OldNurse.last_name.ilike(f"%{term}%"),
            NewNurse.first_name.ilike(f"%{term}%"),
            NewNurse.last_name.ilike(f"%{term}%"),
            OldBed.bed_number.ilike(f"%{term}%"),
            NewBed.bed_number.ilike(f"%{term}%"),
            NurseShiftBedAllocationHistory.shift_name.ilike(f"%{term}%"),
            NurseShiftBedAllocationHistory.remarks.ilike(f"%{term}%"),
            NurseShiftBedAllocationHistory.action.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            n = int(term)
            filters.extend(
                [
                    NurseShiftBedAllocationHistory.id == n,
                    NurseShiftBedAllocationHistory.allocation_id == n,
                ]
            )
        query = query.filter(or_(*filters))

    total = query.count()
    rows = (
        query.order_by(NurseShiftBedAllocationHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Attach relationship aliases for _history_out
    for row in rows:
        row.actor = next((u for u in [row.actor] if u), None)

    # Re-query with joined entities via identity map — use explicit loads
    items = []
    for row in rows:
        actor = db.query(User).filter(User.id == row.actor_id).first() if row.actor_id else None
        old_nurse = (
            db.query(User).filter(User.id == row.old_nurse_id).first()
            if row.old_nurse_id
            else None
        )
        new_nurse = (
            db.query(User).filter(User.id == row.new_nurse_id).first()
            if row.new_nurse_id
            else None
        )
        old_bed = db.query(Bed).filter(Bed.id == row.old_bed_id).first() if row.old_bed_id else None
        new_bed = db.query(Bed).filter(Bed.id == row.new_bed_id).first() if row.new_bed_id else None
        items.append(
            {
                "id": row.id,
                "allocation_id": row.allocation_id,
                "action": row.action,
                "actor_id": row.actor_id,
                "actor_name": _user_label(actor),
                "old_nurse_id": row.old_nurse_id,
                "old_nurse_name": _user_label(old_nurse),
                "new_nurse_id": row.new_nurse_id,
                "new_nurse_name": _user_label(new_nurse),
                "old_bed_id": row.old_bed_id,
                "old_bed_label": _bed_label(old_bed),
                "new_bed_id": row.new_bed_id,
                "new_bed_label": _bed_label(new_bed),
                "shift_date": row.shift_date,
                "shift_name": row.shift_name,
                "remarks": row.remarks,
                "created_at": row.created_at,
            }
        )

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_allocation_dashboard_summary_service(
    db: Session,
    *,
    shift_date: date | None = None,
) -> dict:
    target = shift_date or _now_ist().date()

    total_beds = db.query(func.count(Bed.id)).scalar() or 0
    active_allocs = (
        db.query(func.count(NurseShiftBedAllocation.id))
        .filter(
            NurseShiftBedAllocation.shift_date == target,
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    allocated_bed_ids = {
        row[0]
        for row in db.query(NurseShiftBedAllocation.bed_id)
        .filter(
            NurseShiftBedAllocation.shift_date == target,
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .distinct()
        .all()
    }
    allocated_beds = len(allocated_bed_ids)
    unallocated_beds = max(total_beds - allocated_beds, 0)

    available_nurses = (
        db.query(func.count(User.id))
        .join(Role, Role.id == User.role_id)
        .filter(
            Role.name == "nurse",
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    shift_counts = {name: 0 for name in DEFAULT_SHIFT_TIMES}
    for name, count in (
        db.query(NurseShiftBedAllocation.shift_name, func.count(NurseShiftBedAllocation.id))
        .filter(
            NurseShiftBedAllocation.shift_date == target,
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .group_by(NurseShiftBedAllocation.shift_name)
        .all()
    ):
        key = (name or "").strip()
        if key in shift_counts:
            shift_counts[key] = count
        else:
            shift_counts[key] = count

    coverage = round((allocated_beds / total_beds) * 100, 1) if total_beds else 0.0

    occupied_assigned = 0
    occupied_unassigned = 0
    occupied_beds = (
        db.query(Bed).filter(Bed.status == "occupied", Bed.patient_id.isnot(None)).all()
    )
    for bed in occupied_beds:
        if bed.id in allocated_bed_ids:
            occupied_assigned += 1
        else:
            occupied_unassigned += 1

    return {
        "success": True,
        "shift_date": target,
        "allocated_beds": allocated_beds,
        "unallocated_beds": unallocated_beds,
        "total_beds": total_beds,
        "available_nurses": available_nurses,
        "active_allocations": active_allocs,
        "morning_shift": shift_counts.get("Morning", 0),
        "evening_shift": shift_counts.get("Evening", 0),
        "night_shift": shift_counts.get("Night", 0),
        "shift_counts": shift_counts,
        "coverage_percentage": coverage,
        "occupied_assigned_beds": occupied_assigned,
        "occupied_unassigned_beds": occupied_unassigned,
    }


def get_workload_analytics_service(
    db: Session,
    *,
    shift_date: date | None = None,
    shift_name: str | None = None,
) -> dict:
    target = shift_date or _now_ist().date()

    query = db.query(NurseShiftBedAllocation).filter(
        NurseShiftBedAllocation.shift_date == target,
        NurseShiftBedAllocation.is_active.is_(True),
    )
    if shift_name:
        query = query.filter(
            NurseShiftBedAllocation.shift_name == shift_name.strip()
        )

    rows = query.all()
    bed_ids = list({r.bed_id for r in rows})
    beds_by_id = {
        b.id: b
        for b in (
            db.query(Bed).filter(Bed.id.in_(bed_ids)).all() if bed_ids else []
        )
    }

    by_nurse: dict[int, dict] = {}
    for row in rows:
        entry = by_nurse.setdefault(
            row.nurse_id,
            {"nurse_id": row.nurse_id, "beds": 0, "occupied": 0, "vacant": 0},
        )
        entry["beds"] += 1
        bed = beds_by_id.get(row.bed_id)
        if bed and bed.status == "occupied" and bed.patient_id is not None:
            entry["occupied"] += 1
        else:
            entry["vacant"] += 1

    nurse_ids = list(by_nurse.keys())
    nurses = {
        u.id: u
        for u in (
            db.query(User).filter(User.id.in_(nurse_ids)).all() if nurse_ids else []
        )
    }

    nurse_rows = []
    for nurse_id, stats in by_nurse.items():
        nurse = nurses.get(nurse_id)
        nurse_rows.append(
            {
                **stats,
                "nurse_name": _user_label(nurse),
                "beds_per_nurse": stats["beds"],
            }
        )
    nurse_rows.sort(key=lambda r: r["beds"], reverse=True)

    loads = [r["beds"] for r in nurse_rows]
    avg = round(sum(loads) / len(loads), 2) if loads else 0.0

    dept_dist: dict[str, int] = defaultdict(int)
    for row in rows:
        dept = None
        if row.department_id:
            dept = db.query(Department).filter(Department.id == row.department_id).first()
        name = dept.name if dept else "Unassigned"
        dept_dist[name] += 1

    return {
        "success": True,
        "shift_date": target,
        "shift_name": shift_name,
        "nurses": nurse_rows,
        "average_beds_per_nurse": avg,
        "highest_load": nurse_rows[0] if nurse_rows else None,
        "lowest_load": nurse_rows[-1] if nurse_rows else None,
        "department_distribution": [
            {"department_name": k, "allocation_count": v}
            for k, v in sorted(dept_dist.items(), key=lambda x: -x[1])
        ],
        "total_assigned_beds": sum(loads),
        "total_occupied": sum(r["occupied"] for r in nurse_rows),
        "total_vacant": sum(r["vacant"] for r in nurse_rows),
    }


def detect_allocation_conflicts_service(
    db: Session,
    *,
    shift_date: date | None = None,
) -> dict:
    """Detect issues only — does not modify data."""
    target = shift_date or _now_ist().date()
    warnings: list[dict] = []

    active = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.shift_date == target,
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .all()
    )

    # Duplicate / multiple nurses on same bed+shift
    key_map: dict[tuple, list] = defaultdict(list)
    for row in active:
        key_map[(row.bed_id, row.shift_name)].append(row)

    for (bed_id, shift_name), group in key_map.items():
        if len(group) > 1:
            bed = db.query(Bed).filter(Bed.id == bed_id).first()
            warnings.append(
                {
                    "type": "duplicate_active_assignment",
                    "severity": "high",
                    "message": (
                        f"Multiple active nurses assigned to bed "
                        f"{_bed_label(bed)} for {shift_name} on {target}"
                    ),
                    "allocation_ids": [r.id for r in group],
                    "bed_id": bed_id,
                    "shift_name": shift_name,
                }
            )

    # Overlapping shifts same bed (Morning/Evening/Night windows)
    by_bed: dict[int, list] = defaultdict(list)
    for row in active:
        by_bed[row.bed_id].append(row)

    def _window(row: NurseShiftBedAllocation) -> tuple[time, time] | None:
        start = row.shift_start
        end = row.shift_end
        if start is None or end is None:
            defaults = DEFAULT_SHIFT_TIMES.get(row.shift_name)
            if not defaults:
                return None
            start, end = defaults
        return start, end

    def _overlaps(a: tuple[time, time], b: tuple[time, time]) -> bool:
        a_start, a_end = a
        b_start, b_end = b
        # Overnight shifts: treat as overlapping if either is overnight and shares bed
        def spans(start: time, end: time) -> list[tuple[int, int]]:
            s = start.hour * 60 + start.minute
            e = end.hour * 60 + end.minute
            if start <= end:
                return [(s, e)]
            return [(s, 24 * 60), (0, e)]

        for s1, e1 in spans(a_start, a_end):
            for s2, e2 in spans(b_start, b_end):
                if s1 < e2 and s2 < e1:
                    return True
        return False

    for bed_id, group in by_bed.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                w1 = _window(group[i])
                w2 = _window(group[j])
                if not w1 or not w2:
                    continue
                if group[i].shift_name == group[j].shift_name:
                    continue
                if _overlaps(w1, w2):
                    bed = db.query(Bed).filter(Bed.id == bed_id).first()
                    warnings.append(
                        {
                            "type": "overlapping_shifts",
                            "severity": "medium",
                            "message": (
                                f"Bed {_bed_label(bed)} has overlapping shift windows "
                                f"({group[i].shift_name} / {group[j].shift_name})"
                            ),
                            "allocation_ids": [group[i].id, group[j].id],
                            "bed_id": bed_id,
                        }
                    )

    # Invalid department (bed department mismatch)
    for row in active:
        if row.department_id is None:
            continue
        bed = db.query(Bed).filter(Bed.id == row.bed_id).first()
        if bed and bed.department_id and bed.department_id != row.department_id:
            warnings.append(
                {
                    "type": "invalid_department",
                    "severity": "medium",
                    "message": (
                        f"Allocation #{row.id} department does not match bed "
                        f"{_bed_label(bed)} department"
                    ),
                    "allocation_ids": [row.id],
                    "bed_id": row.bed_id,
                }
            )

    # Expired (shift_date in the past still active) — informational
    today = _now_ist().date()
    expired = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.is_active.is_(True),
            NurseShiftBedAllocation.shift_date < today,
        )
        .limit(50)
        .all()
    )
    for row in expired:
        warnings.append(
            {
                "type": "expired_allocation",
                "severity": "low",
                "message": (
                    f"Active allocation #{row.id} is dated {row.shift_date} (past)"
                ),
                "allocation_ids": [row.id],
                "shift_date": row.shift_date,
            }
        )

    # Inactive nurse still allocated
    for row in active:
        nurse = db.query(User).filter(User.id == row.nurse_id).first()
        if nurse and (nurse.is_active is False or nurse.deleted_at is not None):
            warnings.append(
                {
                    "type": "inactive_nurse",
                    "severity": "high",
                    "message": (
                        f"Allocation #{row.id} assigns inactive/deleted nurse "
                        f"{_user_label(nurse)}"
                    ),
                    "allocation_ids": [row.id],
                    "nurse_id": row.nurse_id,
                }
            )

    return {
        "success": True,
        "shift_date": target,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def get_daily_allocation_report_service(
    db: Session,
    *,
    shift_date: date | None = None,
) -> dict:
    target = shift_date or _now_ist().date()
    summary = get_allocation_dashboard_summary_service(db, shift_date=target)
    rows = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.shift_date == target,
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .order_by(
            NurseShiftBedAllocation.shift_name.asc(),
            NurseShiftBedAllocation.nurse_id.asc(),
        )
        .all()
    )
    from Services.nurse_shift_bed_allocation_service import _allocation_out

    return {
        "success": True,
        "report_type": "daily",
        "shift_date": target,
        "summary": summary,
        "items": [_allocation_out(db, row) for row in rows],
    }


def get_shift_allocation_report_service(
    db: Session,
    *,
    shift_date: date | None = None,
    shift_name: str | None = None,
) -> dict:
    target = shift_date or _now_ist().date()
    query = db.query(NurseShiftBedAllocation).filter(
        NurseShiftBedAllocation.shift_date == target,
        NurseShiftBedAllocation.is_active.is_(True),
    )
    if shift_name:
        query = query.filter(NurseShiftBedAllocation.shift_name == shift_name.strip())
    rows = query.order_by(NurseShiftBedAllocation.nurse_id.asc()).all()
    from Services.nurse_shift_bed_allocation_service import _allocation_out

    return {
        "success": True,
        "report_type": "shift",
        "shift_date": target,
        "shift_name": shift_name,
        "total": len(rows),
        "items": [_allocation_out(db, row) for row in rows],
    }


def get_department_allocation_report_service(
    db: Session,
    *,
    shift_date: date | None = None,
    department_id: int | None = None,
) -> dict:
    target = shift_date or _now_ist().date()
    query = db.query(NurseShiftBedAllocation).filter(
        NurseShiftBedAllocation.shift_date == target,
        NurseShiftBedAllocation.is_active.is_(True),
    )
    if department_id is not None:
        query = query.filter(NurseShiftBedAllocation.department_id == department_id)
    rows = query.all()
    from Services.nurse_shift_bed_allocation_service import _allocation_out

    by_dept: dict[str, list] = defaultdict(list)
    for row in rows:
        out = _allocation_out(db, row)
        key = out.get("department_name") or "Unassigned"
        by_dept[key].append(out)

    return {
        "success": True,
        "report_type": "department",
        "shift_date": target,
        "departments": [
            {"department_name": name, "count": len(items), "items": items}
            for name, items in sorted(by_dept.items())
        ],
    }


def get_unallocated_beds_report_service(
    db: Session,
    *,
    shift_date: date | None = None,
    shift_name: str | None = None,
) -> dict:
    target = shift_date or _now_ist().date()
    allocated_q = db.query(NurseShiftBedAllocation.bed_id).filter(
        NurseShiftBedAllocation.shift_date == target,
        NurseShiftBedAllocation.is_active.is_(True),
    )
    if shift_name:
        allocated_q = allocated_q.filter(
            NurseShiftBedAllocation.shift_name == shift_name.strip()
        )
    allocated_ids = {r[0] for r in allocated_q.distinct().all()}

    beds = db.query(Bed).order_by(Bed.ward_name.asc(), Bed.bed_number.asc()).all()
    items = [
        {
            "bed_id": b.id,
            "bed_number": b.bed_number,
            "ward_name": b.ward_name,
            "department_id": b.department_id,
            "status": b.status,
            "patient_id": b.patient_id,
        }
        for b in beds
        if b.id not in allocated_ids
    ]
    return {
        "success": True,
        "report_type": "unallocated_beds",
        "shift_date": target,
        "shift_name": shift_name,
        "total": len(items),
        "items": items,
    }


def get_unassigned_nurses_report_service(
    db: Session,
    *,
    shift_date: date | None = None,
    shift_name: str | None = None,
) -> dict:
    target = shift_date or _now_ist().date()
    assigned_q = db.query(NurseShiftBedAllocation.nurse_id).filter(
        NurseShiftBedAllocation.shift_date == target,
        NurseShiftBedAllocation.is_active.is_(True),
    )
    if shift_name:
        assigned_q = assigned_q.filter(
            NurseShiftBedAllocation.shift_name == shift_name.strip()
        )
    assigned_ids = {r[0] for r in assigned_q.distinct().all()}

    nurses = (
        db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(
            Role.name == "nurse",
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.first_name.asc(), User.last_name.asc())
        .all()
    )
    items = [
        {
            "nurse_id": n.id,
            "nurse_name": _user_label(n),
            "email": n.email,
        }
        for n in nurses
        if n.id not in assigned_ids
    ]
    return {
        "success": True,
        "report_type": "unassigned_nurses",
        "shift_date": target,
        "shift_name": shift_name,
        "total": len(items),
        "items": items,
    }
