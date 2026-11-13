"""Hospital bed / ward management — inventory is admin-driven (no hardcoded beds)."""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from Models.department import Department
from Models.ipd import IpdAdmission
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory
from Models.opd_billing import Bed
from Models.patient import Patient
from Schemas.opd_schema import AssignBedRequest, BedOut
from Services import opd_helpers as h

IST = ZoneInfo("Asia/Kolkata")
INVENTORY_FILTERS = {"active", "inactive", "all"}


def _normalize_bed_type(bed_type: Optional[str]) -> str:
    value = (bed_type or "single").strip().lower()
    if value not in ("single", "double"):
        raise HTTPException(status_code=400, detail="bed_type must be 'single' or 'double'")
    return value


def _occupied_now(bed: Bed) -> bool:
    return bed.patient_id is not None or (bed.status or "").strip().lower() == "occupied"


def _patient_history_ids(db: Session, bed_ids: list[int]) -> set[int]:
    """Beds that have a current patient or an admitted/discharged stay."""
    if not bed_ids:
        return set()
    found = {
        bed_id
        for (bed_id,) in db.query(IpdAdmission.bed_id)
        .filter(
            IpdAdmission.bed_id.in_(bed_ids),
            IpdAdmission.status.in_(("admitted", "discharged")),
        )
        .distinct()
        .all()
        if bed_id
    }
    found.update(
        bed_id
        for (bed_id,) in db.query(Bed.id)
        .filter(
            Bed.id.in_(bed_ids),
            or_(Bed.patient_id.isnot(None), func.lower(Bed.status) == "occupied"),
        )
        .all()
    )
    return found


def _has_patient_history(db: Session, bed: Bed) -> bool:
    if _occupied_now(bed):
        return True
    stay = (
        db.query(IpdAdmission.id)
        .filter(
            IpdAdmission.bed_id == bed.id,
            IpdAdmission.status.in_(("admitted", "discharged")),
        )
        .first()
    )
    return stay is not None


def _bed_out(
    db: Session,
    bed: Bed,
    has_patient_history: bool | None = None,
) -> BedOut:
    patient = db.query(Patient).filter(Patient.id == bed.patient_id).first() if bed.patient_id else None
    dept = db.query(Department).filter(Department.id == bed.department_id).first()
    if has_patient_history is None:
        has_patient_history = _has_patient_history(db, bed)
    return BedOut(
        id=bed.id,
        bed_number=bed.bed_number,
        ward_name=bed.ward_name,
        bed_type=_normalize_bed_type(getattr(bed, "bed_type", None)),
        department_id=bed.department_id,
        department_name=dept.name if dept else None,
        patient_id=bed.patient_id,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else None,
        patient_uid=patient.patient_uid if patient else None,
        status=bed.status,
        is_active=bool(bed.is_active),
        has_patient_history=bool(has_patient_history),
        admitted_at=bed.admitted_at.isoformat() if bed.admitted_at else None,
    )


def _beds_out(db: Session, beds: list[Bed]) -> list[BedOut]:
    history_ids = _patient_history_ids(db, [bed.id for bed in beds])
    return [_bed_out(db, bed, bed.id in history_ids) for bed in beds]


def _inventory_filter(status_filter: Optional[str]) -> str:
    key = (status_filter or "active").strip().lower()
    if key not in INVENTORY_FILTERS:
        raise HTTPException(
            status_code=422,
            detail="status_filter must be one of: active, inactive, all",
        )
    return key


def _apply_inventory_filter(query, status_filter: Optional[str]):
    key = _inventory_filter(status_filter)
    if key == "active":
        return query.filter(Bed.is_active.is_(True))
    if key == "inactive":
        return query.filter(Bed.is_active.is_(False))
    return query


def _require_active_bed(bed: Bed) -> None:
    if not bed.is_active:
        raise HTTPException(status_code=400, detail="Bed is inactive")


def _deactivate_allocations(db: Session, bed_ids: list[int]) -> None:
    """Stop active nurse assignments for these beds. Keep every stored row."""
    if not bed_ids:
        return
    today = datetime.now(IST).date()
    now = datetime.now(IST)
    rows = (
        db.query(NurseShiftBedAllocation)
        .filter(
            NurseShiftBedAllocation.bed_id.in_(bed_ids),
            NurseShiftBedAllocation.is_active.is_(True),
        )
        .all()
    )
    for row in rows:
        row.is_active = False
        if row.assigned_until is None:
            row.assigned_until = max(today, row.shift_date) if row.shift_date else today
        row.updated_at = now
        db.add(
            NurseShiftBedAllocationHistory(
                allocation_id=row.id,
                action="deactivated",
                old_nurse_id=row.nurse_id,
                new_nurse_id=row.nurse_id,
                old_bed_id=row.bed_id,
                new_bed_id=row.bed_id,
                shift_date=row.shift_date,
                shift_name=row.shift_name,
                remarks="Bed removed from active inventory",
            )
        )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_ward_bed_stats(db: Session) -> list[dict]:
    """Per-ward occupied/available counts for dashboard (single grouped query)."""
    rows = (
        db.query(
            Bed.ward_name,
            func.sum(case((Bed.status == "occupied", 1), else_=0)).label("occupied"),
            func.sum(case((Bed.status == "available", 1), else_=0)).label("available"),
        )
        .filter(Bed.is_active.is_(True))
        .group_by(Bed.ward_name)
        .order_by(Bed.ward_name.asc())
        .all()
    )
    return [
        {
            "ward": ward_name,
            "occupied": int(occupied or 0),
            "available": int(available or 0),
        }
        for ward_name, occupied, available in rows
    ]


def list_beds(
    db: Session,
    ward: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    status_filter: Optional[str] = "active",
) -> dict:
    q = _apply_inventory_filter(db.query(Bed), status_filter)
    if ward and ward.lower() != "all":
        q = q.filter(Bed.ward_name == ward)
    if status and status.lower() != "all":
        q = q.filter(Bed.status == status)

    beds = q.order_by(Bed.ward_name, Bed.bed_number).all()

    if search:
        term = search.lower()
        filtered = []
        for b in beds:
            out = _bed_out(db, b)
            if term in (out.patient_name or "").lower() or term in (out.patient_uid or "").lower():
                filtered.append(b)
            elif term in b.bed_number.lower():
                filtered.append(b)
        beds = filtered

    total = len(beds)
    available = sum(1 for b in beds if b.status == "available")
    occupied = total - available

    return {
        "stats": {"total": total, "available": available, "occupied": occupied},
        "beds": _beds_out(db, beds),
    }


def ward_status(db: Session, ward_name: str) -> dict:
    beds = (
        db.query(Bed)
        .filter(Bed.ward_name == ward_name, Bed.is_active.is_(True))
        .all()
    )
    total = len(beds)
    available = sum(1 for b in beds if b.status == "available")
    return {
        "ward_name": ward_name,
        "occupancy_percent": round((occupied := total - available) / total * 100, 1) if total else 0,
        "stats": {"total": total, "available": available, "occupied": occupied},
        "beds": _beds_out(db, beds),
    }


def assign_bed(db: Session, data: AssignBedRequest) -> BedOut:
    bed = db.query(Bed).filter(Bed.id == data.bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    _require_active_bed(bed)
    if bed.status != "available":
        raise HTTPException(status_code=400, detail="Bed is not available")

    patient = h.get_patient(db, data.patient_id)
    bed.patient_id = patient.id
    bed.status = "occupied"
    bed.admitted_at = h.now_ist()
    if data.department_id:
        bed.department_id = data.department_id

    db.commit()
    db.refresh(bed)
    return _bed_out(db, bed)


def release_bed(db: Session, bed_id: int) -> BedOut:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if not bed.is_active and bed.status != "occupied" and bed.patient_id is None:
        raise HTTPException(status_code=400, detail="Bed is inactive")

    bed.patient_id = None
    bed.status = "available"
    bed.admitted_at = None
    db.commit()
    db.refresh(bed)
    return _bed_out(db, bed)


def _normalize_ward(ward_name: str) -> str:
    name = (ward_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ward name is required")
    return name


def _normalize_bed_number(bed_number: str) -> str:
    num = (bed_number or "").strip()
    if not num:
        raise HTTPException(status_code=400, detail="Bed number is required")
    return num


def _assert_bed_number_unique(db: Session, bed_number: str, exclude_id: Optional[int] = None) -> None:
    q = db.query(Bed).filter(func.lower(Bed.bed_number) == bed_number.lower())
    if exclude_id is not None:
        q = q.filter(Bed.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=409, detail=f"Bed number '{bed_number}' already exists")


def create_bed(db: Session, data) -> BedOut:
    ward = _normalize_ward(data.ward_name)
    number = _normalize_bed_number(data.bed_number)
    _assert_bed_number_unique(db, number)

    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

    bed = Bed(
        bed_number=number,
        ward_name=ward,
        department_id=data.department_id,
        bed_type=_normalize_bed_type(getattr(data, "bed_type", None)),
        status="available",
        is_active=True,
    )
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return _bed_out(db, bed)


def create_beds_bulk(db: Session, data) -> dict:
    ward = _normalize_ward(data.ward_name)
    count = int(data.count or 0)
    if count < 1 or count > 100:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 100")
    start = int(data.start_number or 1)
    if start < 0:
        raise HTTPException(status_code=400, detail="Start number must be >= 0")
    pad = max(0, int(data.pad_width or 0))
    prefix = (data.prefix or "").strip()

    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

    bed_type = _normalize_bed_type(getattr(data, "bed_type", None))

    created = []
    for i in range(count):
        n = start + i
        suffix = str(n).zfill(pad) if pad else str(n)
        number = f"{prefix}{suffix}"
        _assert_bed_number_unique(db, number)
        bed = Bed(
            bed_number=number,
            ward_name=ward,
            department_id=data.department_id,
            bed_type=bed_type,
            status="available",
            is_active=True,
        )
        db.add(bed)
        created.append(bed)

    db.commit()
    for bed in created:
        db.refresh(bed)

    return {
        "ward_name": ward,
        "created_count": len(created),
        "beds": [_bed_out(db, b) for b in created],
    }


def update_bed(db: Session, bed_id: int, data) -> BedOut:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    _require_active_bed(bed)
    if bed.status == "occupied":
        raise HTTPException(
            status_code=400,
            detail="Cannot edit an occupied bed. Release the patient first.",
        )

    if data.bed_number is not None:
        number = _normalize_bed_number(data.bed_number)
        _assert_bed_number_unique(db, number, exclude_id=bed.id)
        bed.bed_number = number
    if data.ward_name is not None:
        bed.ward_name = _normalize_ward(data.ward_name)
    if data.department_id is not None:
        if data.department_id == 0:
            bed.department_id = None
        else:
            dept = db.query(Department).filter(Department.id == data.department_id).first()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found")
            bed.department_id = data.department_id
    if getattr(data, "bed_type", None) is not None:
        bed.bed_type = _normalize_bed_type(data.bed_type)

    db.commit()
    db.refresh(bed)
    return _bed_out(db, bed)


def _purge_unused_bed(db: Session, bed: Bed) -> None:
    """Remove a bed that never had a patient, including nurse rows that point at it."""
    allocation_ids = [
        row_id
        for (row_id,) in db.query(NurseShiftBedAllocation.id)
        .filter(NurseShiftBedAllocation.bed_id == bed.id)
        .all()
    ]
    if allocation_ids:
        db.query(NurseShiftBedAllocationHistory).filter(
            NurseShiftBedAllocationHistory.allocation_id.in_(allocation_ids)
        ).delete(synchronize_session=False)
        db.query(NurseShiftBedAllocation).filter(
            NurseShiftBedAllocation.id.in_(allocation_ids)
        ).delete(synchronize_session=False)
    db.query(NurseShiftBedAllocationHistory).filter(
        NurseShiftBedAllocationHistory.old_bed_id == bed.id
    ).update(
        {NurseShiftBedAllocationHistory.old_bed_id: None},
        synchronize_session=False,
    )
    db.query(NurseShiftBedAllocationHistory).filter(
        NurseShiftBedAllocationHistory.new_bed_id == bed.id
    ).update(
        {NurseShiftBedAllocationHistory.new_bed_id: None},
        synchronize_session=False,
    )
    db.delete(bed)


def delete_bed(db: Session, bed_id: int) -> dict:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed or not bed.is_active:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status == "occupied" or bed.patient_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an occupied bed. Release the patient first.",
        )

    number = bed.bed_number
    ward = bed.ward_name
    if _has_patient_history(db, bed):
        _deactivate_allocations(db, [bed.id])
        bed.is_active = False
        _commit(db)
        return {
            "message": "Bed deactivated successfully",
            "bed_number": number,
            "ward_name": ward,
            "is_active": False,
            "has_patient_history": True,
        }

    _purge_unused_bed(db, bed)
    _commit(db)
    return {
        "message": "Bed deleted",
        "bed_number": number,
        "ward_name": ward,
        "is_active": False,
        "has_patient_history": False,
    }


def activate_bed(db: Session, bed_id: int) -> dict:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.is_active:
        raise HTTPException(status_code=400, detail="Bed is already active")

    bed.is_active = True
    _commit(db)
    return {
        "message": "Bed activated successfully",
        "bed_number": bed.bed_number,
        "ward_name": bed.ward_name,
        "is_active": True,
        "has_patient_history": _has_patient_history(db, bed),
    }


def delete_ward(db: Session, ward_name: str) -> dict:
    """Remove or deactivate a whole ward. Occupied active beds block the action."""
    ward = _normalize_ward(ward_name)
    beds = db.query(Bed).filter(func.lower(Bed.ward_name) == ward.lower()).all()
    active_beds = [bed for bed in beds if bed.is_active]
    if not active_beds:
        raise HTTPException(status_code=404, detail=f"Ward '{ward}' not found")

    occupied = [
        bed for bed in active_beds if bed.status == "occupied" or bed.patient_id is not None
    ]
    if occupied:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete ward '{ward}': {len(occupied)} bed(s) still occupied. "
                "Release patients first."
            ),
        )

    history_ids = _patient_history_ids(db, [bed.id for bed in beds])
    if history_ids:
        _deactivate_allocations(db, [bed.id for bed in active_beds])
        for bed in active_beds:
            bed.is_active = False
        deleted = 0
        deactivated = len(active_beds)
        message = "Ward deactivated successfully"
    else:
        for bed in active_beds:
            _purge_unused_bed(db, bed)
        deleted = len(active_beds)
        deactivated = 0
        message = "Ward deleted"
    _commit(db)
    return {
        "message": message,
        "ward_name": ward,
        "deleted_beds": deleted,
        "deactivated_beds": deactivated,
    }


def activate_ward(db: Session, ward_name: str) -> dict:
    """Turn every inactive bed in the ward back on."""
    ward = _normalize_ward(ward_name)
    beds = db.query(Bed).filter(func.lower(Bed.ward_name) == ward.lower()).all()
    if not beds:
        raise HTTPException(status_code=404, detail=f"Ward '{ward}' not found")
    inactive_beds = [bed for bed in beds if not bed.is_active]
    if not inactive_beds:
        raise HTTPException(status_code=400, detail=f"Ward '{ward}' is already active")

    for bed in inactive_beds:
        bed.is_active = True
    _commit(db)
    return {
        "message": "Ward activated successfully",
        "ward_name": ward,
        "activated_beds": len(inactive_beds),
    }


def ward_inventory_summary(db: Session) -> dict:
    """Ward totals for Admin Settings → OPD bed inventory."""
    rows = (
        db.query(
            Bed.ward_name,
            func.count(Bed.id).label("total"),
            func.sum(case((Bed.status == "available", 1), else_=0)).label("available"),
            func.sum(case((Bed.status == "occupied", 1), else_=0)).label("occupied"),
        )
        .filter(Bed.is_active.is_(True))
        .group_by(Bed.ward_name)
        .order_by(Bed.ward_name.asc())
        .all()
    )
    wards = [
        {
            "ward_name": ward_name,
            "total": int(total or 0),
            "available": int(available or 0),
            "occupied": int(occupied or 0),
        }
        for ward_name, total, available, occupied in rows
    ]
    return {
        "wards": wards,
        "totals": {
            "wards": len(wards),
            "beds": sum(w["total"] for w in wards),
            "available": sum(w["available"] for w in wards),
            "occupied": sum(w["occupied"] for w in wards),
        },
    }


def seed_default_beds(db: Session) -> None:
    """No-op: bed inventory is created only by Admin → Settings → OPD → Beds & wards.

    Kept for backward compatibility with seed.py callers.
    """
    return
