"""Shared helpers for IPD services."""
from datetime import time
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission, IpdBill
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_bed_allocation import NurseShiftBedAllocation
from Models.opd_billing import Bed
from Models.patient import Patient
from Models.user import User
from Services import opd_helpers as oh

_DEFAULT_SHIFT_TIMES = {
    "Morning": (time(6, 0), time(14, 0)),
    "Evening": (time(14, 0), time(22, 0)),
    "Night": (time(22, 0), time(6, 0)),
}


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


def doctor_name_map(db: Session, doctor_ids: list[int] | set[int]) -> dict[int, str]:
    unique = {doctor_id for doctor_id in doctor_ids if doctor_id}
    if not unique:
        return {}
    doctors = db.query(User).filter(User.id.in_(unique)).all()
    return {
        doctor.id: display_name(doctor.first_name, doctor.last_name, prefix="Dr. ")
        for doctor in doctors
    }


def attending_doctors_for_patients(
    db: Session,
    patient_ids: list[int] | set[int],
) -> dict[int, tuple[Optional[int], Optional[str]]]:
    """Latest admitted IPD attending doctor per patient: patient_id -> (doctor_id, doctor_name)."""
    unique = {patient_id for patient_id in patient_ids if patient_id}
    if not unique:
        return {}

    admissions = (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.patient_id.in_(unique),
            IpdAdmission.status == "admitted",
        )
        .order_by(IpdAdmission.admitted_at.desc(), IpdAdmission.id.desc())
        .all()
    )
    latest: dict[int, IpdAdmission] = {}
    for admission in admissions:
        if admission.patient_id not in latest:
            latest[admission.patient_id] = admission

    names = doctor_name_map(
        db,
        [admission.doctor_id for admission in latest.values() if admission.doctor_id],
    )
    return {
        patient_id: (
            admission.doctor_id,
            names.get(admission.doctor_id) if admission.doctor_id else None,
        )
        for patient_id, admission in latest.items()
    }


def nurse_name_map(db: Session, nurse_ids: list[int] | set[int]) -> dict[int, str]:
    unique = {nurse_id for nurse_id in nurse_ids if nurse_id}
    if not unique:
        return {}
    nurses = db.query(User).filter(User.id.in_(unique)).all()
    return {
        nurse.id: display_name(nurse.first_name, nurse.last_name)
        for nurse in nurses
    }


def _shift_window_covers(now_t: time, start: time | None, end: time | None) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_t < end
    return now_t >= start or now_t < end


def _allocation_shift_times(row: NurseShiftBedAllocation) -> tuple[time | None, time | None]:
    start, end = row.shift_start, row.shift_end
    if start is not None or end is not None:
        return start, end
    return _DEFAULT_SHIFT_TIMES.get(row.shift_name, (None, None))


def _pick_allocation_for_bed(
    rows: list[NurseShiftBedAllocation],
    now_t: time,
) -> NurseShiftBedAllocation | None:
    if not rows:
        return None
    covering = [row for row in rows if _shift_window_covers(now_t, *_allocation_shift_times(row))]
    if covering:
        return covering[0]
    return rows[0]


def allocated_nurses_for_patients(
    db: Session,
    patient_ids: list[int] | set[int],
) -> dict[int, tuple[Optional[int], Optional[str]]]:
    """Assigned nurse per patient, mirroring attending_doctors_for_patients.

    Prefer the nurse currently allocated to the occupied bed (active shift
    allocation). If none, fall back to the latest vitals recorder, then the
    latest nursing-note author. patient_id -> (nurse_id, nurse_name).
    """
    unique = {patient_id for patient_id in patient_ids if patient_id}
    if not unique:
        return {}

    chosen: dict[int, int] = {}

    occupied_beds: dict[int, Bed] = {}
    for bed in (
        db.query(Bed)
        .filter(
            Bed.patient_id.in_(unique),
            Bed.status == "occupied",
            Bed.patient_id.isnot(None),
        )
        .order_by(Bed.admitted_at.desc())
        .all()
    ):
        if bed.patient_id not in occupied_beds:
            occupied_beds[bed.patient_id] = bed

    bed_to_patient = {bed.id: patient_id for patient_id, bed in occupied_beds.items()}
    bed_ids = list(bed_to_patient.keys())
    if bed_ids:
        today = now_ist().date()
        now_t = now_ist().timetz().replace(tzinfo=None)
        allocations = (
            db.query(NurseShiftBedAllocation)
            .filter(
                NurseShiftBedAllocation.bed_id.in_(bed_ids),
                NurseShiftBedAllocation.is_active.is_(True),
                NurseShiftBedAllocation.shift_date <= today,
                or_(
                    NurseShiftBedAllocation.assigned_until.is_(None),
                    NurseShiftBedAllocation.assigned_until >= today,
                ),
            )
            .order_by(NurseShiftBedAllocation.id.desc())
            .all()
        )
        by_bed: dict[int, list[NurseShiftBedAllocation]] = {}
        for row in allocations:
            by_bed.setdefault(row.bed_id, []).append(row)
        for bed_id, rows in by_bed.items():
            patient_id = bed_to_patient.get(bed_id)
            picked = _pick_allocation_for_bed(rows, now_t)
            if patient_id and picked and picked.nurse_id:
                chosen[patient_id] = picked.nurse_id

    missing = unique - set(chosen.keys())
    if missing:
        for patient_id, recorded_by in (
            db.query(PatientVitals.patient_id, PatientVitals.recorded_by)
            .filter(PatientVitals.patient_id.in_(missing))
            .order_by(
                PatientVitals.patient_id,
                PatientVitals.recorded_at.desc(),
                PatientVitals.id.desc(),
            )
            .distinct(PatientVitals.patient_id)
            .all()
        ):
            if patient_id not in chosen and recorded_by:
                chosen[patient_id] = recorded_by
        missing = unique - set(chosen.keys())

    if missing:
        for patient_id, nurse_id in (
            db.query(NursingNote.patient_id, NursingNote.nurse_id)
            .filter(NursingNote.patient_id.in_(missing))
            .order_by(
                NursingNote.patient_id,
                NursingNote.created_at.desc(),
                NursingNote.id.desc(),
            )
            .distinct(NursingNote.patient_id)
            .all()
        ):
            if patient_id not in chosen and nurse_id:
                chosen[patient_id] = nurse_id

    names = nurse_name_map(db, list(chosen.values()))
    return {
        patient_id: (nurse_id, names.get(nurse_id))
        for patient_id, nurse_id in chosen.items()
    }
