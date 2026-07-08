"""Hospital bed / ward management."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from Models.department import Department
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


def seed_default_beds(db: Session) -> None:
    if db.query(Bed).count() > 0:
        return
    wards = [
        ("General", ["G-101", "G-102", "G-103", "G-104"]),
        ("ICU", ["ICU-1", "ICU-2"]),
        ("Private", ["P-201", "P-202"]),
    ]
    for ward, numbers in wards:
        for num in numbers:
            db.add(Bed(bed_number=num, ward_name=ward, status="available"))
    db.commit()