"""Hospital bed / ward management — inventory is admin-driven (no hardcoded beds)."""
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from Models.department import Department
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.nurse_shift_bed_allocation_history import NurseShiftBedAllocationHistory
from Models.opd_billing import Bed
from Models.patient import Patient
from Schemas.opd_schema import AssignBedRequest, BedOut
from Services import opd_helpers as h


def _bed_out(db: Session, bed: Bed) -> BedOut:
    patient = db.query(Patient).filter(Patient.id == bed.patient_id).first() if bed.patient_id else None
    dept = db.query(Department).filter(Department.id == bed.department_id).first()
    return BedOut(
        id=bed.id,
        bed_number=bed.bed_number,
        ward_name=bed.ward_name,
        department_id=bed.department_id,
        department_name=dept.name if dept else None,
        patient_id=bed.patient_id,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else None,
        patient_uid=patient.patient_uid if patient else None,
        status=bed.status,
        admitted_at=bed.admitted_at.isoformat() if bed.admitted_at else None,
    )


def get_ward_bed_stats(db: Session) -> list[dict]:
    """Per-ward occupied/available counts for dashboard (single grouped query)."""
    rows = (
        db.query(
            Bed.ward_name,
            func.sum(case((Bed.status == "occupied", 1), else_=0)).label("occupied"),
            func.sum(case((Bed.status == "available", 1), else_=0)).label("available"),
        )
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
) -> dict:
    q = db.query(Bed)
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
        "beds": [_bed_out(db, b) for b in beds],
    }


def ward_status(db: Session, ward_name: str) -> dict:
    beds = db.query(Bed).filter(Bed.ward_name == ward_name).all()
    total = len(beds)
    available = sum(1 for b in beds if b.status == "available")
    return {
        "ward_name": ward_name,
        "occupancy_percent": round((occupied := total - available) / total * 100, 1) if total else 0,
        "stats": {"total": total, "available": available, "occupied": occupied},
        "beds": [_bed_out(db, b) for b in beds],
    }


def assign_bed(db: Session, data: AssignBedRequest) -> BedOut:
    bed = db.query(Bed).filter(Bed.id == data.bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
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
        status="available",
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
            status="available",
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

    db.commit()
    db.refresh(bed)
    return _bed_out(db, bed)


def _detach_bed_references(db: Session, bed_ids: list[int]) -> None:
    """Clear nurse allocation FKs so inventory deletes propagate cleanly everywhere."""
    if not bed_ids:
        return

    db.query(NurseShiftBedAllocationHistory).filter(
        NurseShiftBedAllocationHistory.old_bed_id.in_(bed_ids)
    ).update(
        {NurseShiftBedAllocationHistory.old_bed_id: None},
        synchronize_session=False,
    )
    db.query(NurseShiftBedAllocationHistory).filter(
        NurseShiftBedAllocationHistory.new_bed_id.in_(bed_ids)
    ).update(
        {NurseShiftBedAllocationHistory.new_bed_id: None},
        synchronize_session=False,
    )

    today = date.today()
    allocs = (
        db.query(NurseShiftBedAllocation)
        .filter(NurseShiftBedAllocation.bed_id.in_(bed_ids))
        .all()
    )
    for row in allocs:
        row.is_active = False
        if row.assigned_until is None:
            row.assigned_until = today
        db.delete(row)


def delete_bed(db: Session, bed_id: int) -> dict:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status == "occupied" or bed.patient_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an occupied bed. Release the patient first.",
        )

    number = bed.bed_number
    ward = bed.ward_name
    _detach_bed_references(db, [bed.id])
    db.delete(bed)
    db.commit()
    return {"message": "Bed deleted", "bed_number": number, "ward_name": ward}


def delete_ward(db: Session, ward_name: str) -> dict:
    """Remove a ward and all its beds. Blocked if any bed is occupied."""
    ward = _normalize_ward(ward_name)
    beds = db.query(Bed).filter(func.lower(Bed.ward_name) == ward.lower()).all()
    if not beds:
        raise HTTPException(status_code=404, detail=f"Ward '{ward}' not found")

    occupied = [b for b in beds if b.status == "occupied" or b.patient_id is not None]
    if occupied:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete ward '{ward}': {len(occupied)} bed(s) still occupied. "
                "Release patients first."
            ),
        )

    bed_ids = [b.id for b in beds]
    deleted = len(beds)
    _detach_bed_references(db, bed_ids)
    for bed in beds:
        db.delete(bed)
    db.commit()
    return {"message": "Ward deleted", "ward_name": ward, "deleted_beds": deleted}


def ward_inventory_summary(db: Session) -> dict:
    """Ward totals for Admin Settings → OPD bed inventory."""
    rows = (
        db.query(
            Bed.ward_name,
            func.count(Bed.id).label("total"),
            func.sum(case((Bed.status == "available", 1), else_=0)).label("available"),
            func.sum(case((Bed.status == "occupied", 1), else_=0)).label("occupied"),
        )
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
