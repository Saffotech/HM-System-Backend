"""Shared helpers for IPD services."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission, IpdBill
from Models.opd_billing import Bed
from Models.patient import Patient
from Models.user import User
from Services import opd_helpers as oh


def now_ist():
    return oh.now_ist()


def display_name(first: str, last: Optional[str] = None, prefix: str = "") -> str:
    return oh.display_name(first, last, prefix)


def get_patient(db: Session, patient_id: int) -> Patient:
    return oh.get_patient(db, patient_id)


def next_admission_no(db: Session) -> str:
    """Short admission id — same pattern as patient UHID (P-1028 → IPD-1001)."""
    last = db.query(func.max(IpdAdmission.id)).scalar() or 0
    return f"IPD-{1000 + last + 1}"


def next_ipd_bill_number(db: Session) -> str:
    last = db.query(func.max(IpdBill.id)).scalar() or 0
    return f"IPD-BILL-{last + 1:05d}"


def get_admission(db: Session, admission_id: int) -> IpdAdmission:
    row = db.query(IpdAdmission).filter(IpdAdmission.id == admission_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="IPD admission not found")
    return row


def get_active_admission_for_patient(db: Session, patient_id: int) -> Optional[IpdAdmission]:
    return (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.patient_id == patient_id,
            IpdAdmission.status == "admitted",
        )
        .order_by(IpdAdmission.admitted_at.desc())
        .first()
    )


def get_active_admission_for_bed(db: Session, bed_id: int) -> Optional[IpdAdmission]:
    return (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.bed_id == bed_id,
            IpdAdmission.status == "admitted",
        )
        .first()
    )


def ensure_admission_for_occupied_bed(
    db: Session, bed: Bed, admitted_by: Optional[int] = None
) -> IpdAdmission:
    """
    Occupied beds may exist without an IpdAdmission (legacy / inventory assign).
    Transfer, discharge, and billing need an admission — create or re-link one.
    """
    if bed.status != "occupied" or not bed.patient_id:
        raise HTTPException(
            status_code=400,
            detail="Bed has no active patient occupancy to transfer",
        )

    by_bed = get_active_admission_for_bed(db, bed.id)
    if by_bed:
        return by_bed

    by_patient = get_active_admission_for_patient(db, bed.patient_id)
    if by_patient:
        # Keep a single active admission; point it at this occupied bed.
        by_patient.bed_id = bed.id
        by_patient.ward_name = bed.ward_name
        by_patient.bed_number = bed.bed_number
        if bed.department_id and not by_patient.department_id:
            by_patient.department_id = bed.department_id
        db.flush()
        return by_patient

    admission = IpdAdmission(
        admission_no=next_admission_no(db),
        patient_id=bed.patient_id,
        bed_id=bed.id,
        doctor_id=None,
        department_id=bed.department_id,
        ward_name=bed.ward_name,
        bed_number=bed.bed_number,
        diagnosis=None,
        notes="Auto-created from occupied bed (no prior IPD admission)",
        status="admitted",
        admitted_at=bed.admitted_at or now_ist(),
        admitted_by=admitted_by,
    )
    db.add(admission)
    db.flush()
    return admission


def occupy_bed(db: Session, bed: Bed, patient_id: int, department_id: Optional[int] = None) -> None:
    if bed.status != "available":
        raise HTTPException(status_code=400, detail="Bed is not available")
    bed.patient_id = patient_id
    bed.status = "occupied"
    bed.admitted_at = now_ist()
    if department_id:
        bed.department_id = department_id


def free_bed(db: Session, bed: Optional[Bed]) -> None:
    if not bed:
        return
    bed.patient_id = None
    bed.status = "available"
    bed.admitted_at = None


def get_bed(db: Session, bed_id: int) -> Bed:
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    return bed


def doctor_display(db: Session, doctor_id: Optional[int]) -> Optional[str]:
    if not doctor_id:
        return None
    doctor = db.query(User).filter(User.id == doctor_id).first()
    if not doctor:
        return None
    return display_name(doctor.first_name, doctor.last_name, prefix="Dr. ")
