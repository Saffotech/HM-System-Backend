"""Shared helpers for nurse module services."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, Bed
from Models.patient import Patient
from Models.user import User

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_start_ist() -> datetime:
    return now_ist().replace(hour=0, minute=0, second=0, microsecond=0)


def display_name(first: str | None, last: str | None = None) -> str:
    return f"{first or ''} {last or ''}".strip()


def user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return display_name(user.first_name, user.last_name) or None


def patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return display_name(patient.first_name, patient.last_name) or None


def occupied_bed_for_patient(db: Session, patient_id: int) -> Bed | None:
    return (
        db.query(Bed)
        .filter(
            Bed.patient_id == patient_id,
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .first()
    )


def occupied_beds_map(db: Session, patient_ids: set[int]) -> dict[int, Bed]:
    if not patient_ids:
        return {}
    beds: dict[int, Bed] = {}
    for bed in (
        db.query(Bed)
        .filter(
            Bed.patient_id.in_(patient_ids),
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .all()
    ):
        if bed.patient_id not in beds:
            beds[bed.patient_id] = bed
    return beds


def patient_bed_snapshot(db: Session, patient_id: int) -> dict[str, Optional[str]]:
    bed = occupied_bed_for_patient(db, patient_id)
    if not bed:
        return {"ward_name": None, "bed_number": None}
    return {"ward_name": bed.ward_name, "bed_number": bed.bed_number}


def resolve_patient_and_appointment(
    db: Session,
    *,
    appointment_id: int | None,
    patient_id: int | None,
) -> tuple[Patient, Appointment | None]:
    """
    OPD: resolve via appointment_id.
    IPD: allow patient_id when the patient occupies a bed.
    """
    if appointment_id is not None:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if patient_id is not None and patient_id != appointment.patient_id:
            raise HTTPException(
                status_code=400,
                detail="patient_id does not match appointment",
            )
        patient = (
            db.query(Patient)
            .filter(Patient.id == appointment.patient_id)
            .first()
        )
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient, appointment

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active.is_(True))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not occupied_bed_for_patient(db, patient.id):
        raise HTTPException(
            status_code=400,
            detail=(
                "patient_id is only allowed for patients currently occupying a bed, "
                "or provide appointment_id"
            ),
        )

    return patient, None
