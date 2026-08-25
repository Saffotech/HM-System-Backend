"""Sync nurse-logged doctor visits → billable IpdDoctorVisit rows (fee snapshot)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission, IpdDoctorVisit
from Models.nurse_doctor_visit import NurseDoctorVisit
from Models.user import User
from Services import opd_settings_service


def get_active_admission_for_patient(db: Session, patient_id: int) -> Optional[IpdAdmission]:
    """Latest open admission for patient (billing belongs to a stay)."""
    return (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.patient_id == patient_id,
            IpdAdmission.status == "admitted",
        )
        .order_by(IpdAdmission.admitted_at.desc(), IpdAdmission.id.desc())
        .first()
    )


def resolve_visit_charge(
    db: Session,
    *,
    doctor: User,
    admission: IpdAdmission,
) -> float:
    """Freeze consultation fee at visit create/update (doctor → dept → hospital)."""
    pricing = opd_settings_service.get_pricing(db)
    return float(
        opd_settings_service.resolve_consultation_fee(
            pricing,
            doctor_id=doctor.id,
            department_id=admission.department_id or doctor.department_id,
        )
    )


def upsert_ipd_visit_from_nurse(
    db: Session,
    *,
    nurse_visit: NurseDoctorVisit,
    doctor: User,
    recorded_by: int,
) -> Optional[IpdDoctorVisit]:
    """
    Ensure a billable IPD visit exists for this nurse log when patient is admitted.
    If already linked but patient is no longer admitted, keep the historical row
    and refresh doctor/notes/time (charge stays on original admission context).
    """
    existing = (
        db.query(IpdDoctorVisit)
        .filter(IpdDoctorVisit.nurse_visit_id == nurse_visit.id)
        .first()
    )
    admission = get_active_admission_for_patient(db, nurse_visit.patient_id)

    visited_at = nurse_visit.visited_at
    if isinstance(visited_at, datetime) and visited_at.tzinfo is None:
        from zoneinfo import ZoneInfo

        visited_at = visited_at.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

    if not admission:
        if existing and not existing.is_voided:
            existing.doctor_id = doctor.id
            existing.visited_at = visited_at
            existing.notes = nurse_visit.notes
            existing.recorded_by = recorded_by
            return existing
        return None

    charge = resolve_visit_charge(db, doctor=doctor, admission=admission)

    if existing:
        existing.admission_id = admission.id
        existing.doctor_id = doctor.id
        existing.visited_at = visited_at
        existing.charge = charge
        existing.notes = nurse_visit.notes
        existing.is_voided = False
        existing.recorded_by = recorded_by
        return existing

    row = IpdDoctorVisit(
        admission_id=admission.id,
        doctor_id=doctor.id,
        visited_at=visited_at,
        charge=charge,
        notes=nurse_visit.notes,
        recorded_by=recorded_by,
        nurse_visit_id=nurse_visit.id,
        is_voided=False,
    )
    db.add(row)
    return row


def void_ipd_visit_from_nurse(db: Session, nurse_visit_id: int) -> None:
    """Soft-void linked billable visit (keeps audit; excluded from bill preview)."""
    row = (
        db.query(IpdDoctorVisit)
        .filter(IpdDoctorVisit.nurse_visit_id == nurse_visit_id)
        .first()
    )
    if row and not row.is_voided:
        row.is_voided = True
