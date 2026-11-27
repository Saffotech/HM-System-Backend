"""Profile tab for a signed-in patient.

Header and Personal Records come from the patients row (the same row the
desk uses). Hospital Records and Billing live in their own services; the
summary here only gathers their counts for the profile landing screen.
"""

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import Patient
from Models.tenant import Tenant
from Models.user import User
from Schemas.patient_profile_schema import PatientProfileUpdate
from Services import opd_helpers as opd_h
from Services import patient_billing_service, patient_history_service
from Services.patient_portal_service import patient_for_user

# Optional free-text fields: stored trimmed, empty means "cleared".
_TEXT_FIELDS = (
    "address",
    "state",
    "blood_group",
    "allergies",
    "insurance_policy_no",
    "emergency_contact_name",
    "emergency_contact_relation",
)


def _age(date_of_birth: date | None) -> int | None:
    if date_of_birth is None:
        return None
    today = opd_h.now_ist().date()
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def _self_registered(patient: Patient) -> bool:
    """Self sign-up records the patient's own login as the registrar.

    A desk registration records a staff user instead.
    """
    return patient.user_id is not None and patient.registered_by == patient.user_id


def _hospital(db: Session, tenant_id: int | None) -> dict | None:
    if tenant_id is None:
        return None
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        return None
    return {
        "id": tenant.id,
        "name": tenant.name,
        "code": tenant.code,
        "phone": tenant.phone,
        "email": tenant.email,
        "address": tenant.address,
        "city": tenant.city,
    }


def get_profile(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    return {
        "user_id": user.id,
        "patient_id": patient.id,
        "patient_uid": patient.patient_uid,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "full_name": opd_h.display_name(patient.first_name, patient.last_name),
        "email": user.email,
        "phone": patient.phone,
        "gender": patient.gender,
        "date_of_birth": patient.date_of_birth,
        "age": _age(patient.date_of_birth),
        "blood_group": patient.blood_group,
        "address": patient.address,
        "state": patient.state,
        "allergies": patient.allergies,
        "insurance_policy_no": patient.insurance_policy_no,
        "emergency_contact": {
            "name": patient.emergency_contact_name,
            "phone": patient.emergency_contact_phone,
            "relation": patient.emergency_contact_relation,
        },
        "self_registered": _self_registered(patient),
        "registered_at": patient.created_at,
        "hospital": _hospital(db, patient.tenant_id),
    }


def _phone_digits(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 10:
        raise HTTPException(status_code=422, detail="Phone must be at least 10 digits")
    return digits[-15:]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def update_profile(db: Session, user: User, data: PatientProfileUpdate) -> dict:
    """Apply only the fields the patient sent."""
    patient = patient_for_user(db, user)
    changes = data.model_dump(exclude_unset=True)

    if "phone" in changes:
        phone = _clean(changes["phone"])
        if phone is None:
            raise HTTPException(status_code=422, detail="Phone cannot be empty")
        patient.phone = user.phone = _phone_digits(phone)

    if "emergency_contact_phone" in changes:
        raw = _clean(changes["emergency_contact_phone"])
        patient.emergency_contact_phone = _phone_digits(raw) if raw else None

    for field in _TEXT_FIELDS:
        if field in changes:
            setattr(patient, field, _clean(changes[field]))

    db.commit()
    return get_profile(db, user)


def get_summary(db: Session, user: User) -> dict:
    """Counts and balance for the profile landing screen, in one call."""
    patient = patient_for_user(db, user)
    opd = patient_history_service.opd_history(db, user)
    ipd = patient_history_service.ipd_history(db, user)
    outstanding, _ = patient_billing_service.outstanding_balance(db, patient.id)
    upcoming = (
        db.query(Appointment.id)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.status == AppointmentStatus.scheduled,
            Appointment.scheduled_at >= datetime.now(opd_h.IST),
        )
        .count()
    )
    return {
        "opd_visits": opd["total"],
        "latest_visit": opd["visits"][0] if opd["visits"] else None,
        "ipd_admissions": ipd["total"],
        "currently_admitted": ipd["current_admission"] is not None,
        "receipts": len(patient_billing_service.receipts(db, patient.id)),
        "outstanding_balance": outstanding,
        "upcoming_appointments": upcoming,
    }
