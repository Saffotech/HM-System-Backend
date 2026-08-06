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
    last = db.query(func.max(IpdAdmission.id)).scalar() or 0
    today = now_ist().strftime("%Y%m%d")
    return f"IPD-{today}-{last + 1:04d}"


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
