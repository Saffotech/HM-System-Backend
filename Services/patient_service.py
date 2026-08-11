"""
Shared Patient Master — create/lookup demographics only.

Does NOT create OPD visits, appointments, tokens, or bills.
OPD and IPD both use this for the hospital Patient record (UHID).
"""
from typing import Optional, Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.patient import Patient
from Schemas.patient_schema import PatientOut, gender_code_to_label
from Services import opd_helpers as h


class PatientDemographics(Protocol):
    first_name: str
    phone: str
    last_name: Optional[str]
    gender: Optional[int]
    blood_group: Optional[str]
    date_of_birth: Optional[object]
    address: Optional[str]
    state: Optional[str]
    aadhaar_number: Optional[str]
    email: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    allergies: Optional[str]
    insurance_policy_no: Optional[str]


def patient_to_model(data: PatientDemographics, patient_uid: str, registered_by: int) -> Patient:
    return Patient(
        patient_uid=patient_uid,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        gender=gender_code_to_label(data.gender),
        blood_group=data.blood_group,
        phone=data.phone,
        email=data.email,
        address=data.address,
        state=data.state,
        aadhaar_number=data.aadhaar_number,
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=data.emergency_contact_phone,
        allergies=data.allergies,
        insurance_policy_no=data.insurance_policy_no,
        registered_by=registered_by,
    )


def _ensure_aadhaar_unique(db: Session, aadhaar: str) -> None:
    existing = (
        db.query(Patient)
        .filter(
            Patient.aadhaar_number == aadhaar,
            Patient.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Patient with this Aadhaar already exists. UID: {existing.patient_uid}",
        )


def create_patient_record(
    db: Session,
    data: PatientDemographics,
    registered_by: int,
    *,
    require_aadhaar: bool = True,
    commit: bool = True,
) -> Patient:
    """
    Create a Patient master row only (UHID + demographics).

    When commit=False the caller owns the transaction (e.g. OPD register+visit).
    """
    aadhaar_raw = getattr(data, "aadhaar_number", None)
    if require_aadhaar and not aadhaar_raw:
        raise HTTPException(status_code=422, detail="Aadhaar number is required")

    if aadhaar_raw:
        aadhaar = h.normalize_aadhaar(aadhaar_raw)
        _ensure_aadhaar_unique(db, aadhaar)
        if hasattr(data, "model_copy"):
            data = data.model_copy(update={"aadhaar_number": aadhaar})
        else:
            # Plain objects / Protocol — set attribute if mutable
            try:
                data.aadhaar_number = aadhaar  # type: ignore[attr-defined]
            except Exception:
                pass

    patient = patient_to_model(data, h.next_patient_uid(db), registered_by)
    db.add(patient)
    db.flush()

    if commit:
        db.commit()
        db.refresh(patient)

    return patient


def register_patient_only(
    db: Session,
    data: PatientDemographics,
    registered_by: int,
) -> PatientOut:
    """Public entry: patient master registration with no visit/bill side effects."""
    patient = create_patient_record(
        db,
        data,
        registered_by,
        require_aadhaar=True,
        commit=True,
    )
    return PatientOut.model_validate(patient)
