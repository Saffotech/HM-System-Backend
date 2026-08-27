"""Shared helpers for doctor module (OPD appointments + patients)."""
import re
from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.opd_billing import Appointment
from Models.ipd import IpdAdmission
from Models.patient import Patient, registration_source_value
from Services.ipd_helpers import allocated_nurses_for_patients

IST = ZoneInfo("Asia/Kolkata")


def day_bounds(on_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(on_date, time.min, tzinfo=IST)
    end = datetime.combine(on_date, time.max, tzinfo=IST)
    return start, end


def scheduled_on_date(on_date: date):
    start, end = day_bounds(on_date)
    return and_(Appointment.scheduled_at >= start, Appointment.scheduled_at <= end)


def admitted_on_date(on_date: date):
    start, end = day_bounds(on_date)
    return and_(IpdAdmission.admitted_at >= start, IpdAdmission.admitted_at <= end)


def admitted_between(from_date: Optional[date] = None, to_date: Optional[date] = None):
    clauses = []
    if from_date:
        start, _ = day_bounds(from_date)
        clauses.append(IpdAdmission.admitted_at >= start)
    if to_date:
        _, end = day_bounds(to_date)
        clauses.append(IpdAdmission.admitted_at <= end)
    if not clauses:
        return None
    return and_(*clauses)


def display_name(first: str, last: Optional[str] = None) -> str:
    return f"{first} {last or ''}".strip()


def with_nurse_names(db: Session, items: List[dict]) -> List[dict]:
    """Attach assigned nurse_id / nurse_name onto doctor patient rows."""
    if not items:
        return items
    mapping = allocated_nurses_for_patients(
        db,
        [item.get("patient_id") for item in items],
    )
    for item in items:
        nurse_id, nurse_name = mapping.get(item.get("patient_id"), (None, None))
        item["nurse_id"] = nurse_id
        item["nurse_name"] = nurse_name
    return items


def patient_age(date_of_birth: Optional[date]) -> Optional[int]:
    """Completed whole years (0 for infants under 1 year)."""
    if not date_of_birth:
        return None
    today = datetime.now(IST).date()
    if date_of_birth > today:
        return None
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def _patient_age_months(date_of_birth: date, today: date) -> int:
    months = (today.year - date_of_birth.year) * 12 + (today.month - date_of_birth.month)
    if today.day < date_of_birth.day:
        months -= 1
    return max(months, 0)


def format_patient_age_label(date_of_birth: Optional[date]) -> Optional[str]:
    """
    Doctor-facing age label:
    - under 1 month → Nd (days)
    - under 1 year → Nm (months)
    - otherwise → Ny (years)
    """
    if not date_of_birth:
        return None
    today = datetime.now(IST).date()
    if date_of_birth > today:
        return None

    years = patient_age(date_of_birth)
    if years is None:
        return None
    if years >= 1:
        return f"{years}y"

    months = _patient_age_months(date_of_birth, today)
    if months < 1:
        days = (today - date_of_birth).days
        return f"{max(days, 0)}d"
    return f"{months}m"


_GENDER_LABELS = {
    1: "Male",
    2: "Female",
    3: "Other",
    4: "Prefer not to say",
    "1": "Male",
    "2": "Female",
    "3": "Other",
    "4": "Prefer not to say",
}


def _gender_label(gender) -> Optional[str]:
    if gender is None:
        return None
    if gender in _GENDER_LABELS:
        return _GENDER_LABELS[gender]
    text = str(gender).strip()
    if not text:
        return None
    if text in _GENDER_LABELS:
        return _GENDER_LABELS[text]
    return text


def patient_age_fields(date_of_birth: Optional[date], gender) -> dict:
    """
    Build patient_age / patient_gender for doctor APIs.

    Frontend Patients list always renders age as ``{age}y``, so under-1-year
    labels (Nd / Nm) are placed in patient_gender with the real gender so the
    Age/Gender cell shows correctly without frontend changes.
    """
    years = patient_age(date_of_birth)
    label = format_patient_age_label(date_of_birth)
    gender_text = _gender_label(gender)

    if label is None:
        return {"patient_age": None, "patient_gender": gender_text}

    # Adults / 1y+: keep numeric years — UI appends "y" → "25y"
    if years is not None and years >= 1:
        return {"patient_age": years, "patient_gender": gender_text}

    # Infants: UI would turn "6m" into "6my", so compose into gender channel
    if gender_text:
        return {"patient_age": None, "patient_gender": f"{label} · {gender_text}"}
    return {"patient_age": None, "patient_gender": label}


def get_patient(db: Session, patient_id: int) -> Optional[Patient]:
    return (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active.is_(True))
        .first()
    )


_INTERNAL_APPOINTMENT_MARKERS = (
    "[pay-later]",
    "booked during registration",
    "new patient registration",
    "opd revisit",
)


def strip_internal_appointment_markers(text: Optional[str]) -> Optional[str]:
    """Hide OPD booking markers from doctor-facing clinical fields."""
    if text is None:
        return None
    cleaned = str(text)
    for marker in _INTERNAL_APPOINTMENT_MARKERS:
        cleaned = re.sub(re.escape(marker), "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or None

def appointment_to_dict(
    db: Session,
    apt: Appointment,
    patient: Optional[Patient] = None,
) -> dict:
    if patient is None:
        patient = get_patient(db, apt.patient_id)

    scheduled = apt.scheduled_at
    age_fields = patient_age_fields(
        patient.date_of_birth if patient else None,
        patient.gender if patient else None,
    )
    return {
        "id": apt.id,
        "appointment_uid": apt.appointment_uid,
        "patient_id": apt.patient_id,
        "patient_name": display_name(patient.first_name, patient.last_name) if patient else "",
        "patient_phone": patient.phone if patient else "",
        "patient_age": age_fields["patient_age"],
        "patient_gender": age_fields["patient_gender"],
        "patient_uid": patient.patient_uid if patient else "",
        "registration_source": registration_source_value(
            getattr(patient, "registration_source", None)
        ),
        "doctor_id": apt.doctor_id,
        "department_id": apt.department_id,
        "scheduled_at": scheduled.isoformat() if scheduled else None,
        "appointment_date": scheduled.date().isoformat() if scheduled else None,
        "appointment_time": scheduled.strftime("%H:%M:%S") if scheduled else None,
        "appointment_type": apt.appointment_type,
        "encounter_type": "OPD",
        "admission_id": None,
        "bed_number": None,
        "ward_name": None,
        "status": getattr(apt.status, "value", apt.status),
        "reason": strip_internal_appointment_markers(apt.reason),
        "symptoms": getattr(apt, "symptoms", None),
        "notes": strip_internal_appointment_markers(apt.notes),
        "diagnosis": getattr(apt, "diagnosis", None),
        "follow_up": (
            apt.follow_up_date.isoformat()
            if getattr(apt, "follow_up_date", None)
            else None
        ),
        "admitted_at": None,
        "discharged_at": None,
        "created_at": apt.created_at.isoformat() if apt.created_at else None,
        "nurse_id": None,
        "nurse_name": None,
    }


def appointments_to_dicts(db: Session, rows: List[Appointment]) -> List[dict]:
    patient_cache: dict[int, Patient] = {}
    out = []
    for apt in rows:
        pid = apt.patient_id
        if pid not in patient_cache:
            patient_cache[pid] = get_patient(db, pid)
        out.append(appointment_to_dict(db, apt, patient_cache.get(pid)))
    return with_nurse_names(db, out)


def admission_to_dict(
    db: Session,
    admission: IpdAdmission,
    patient: Optional[Patient] = None,
    *,
    use_dashboard_status: bool = False,
) -> dict:
    """IPD row in the same shape as appointment_to_dict.

    Uses a non-numeric appointment_uid (admission_no) so existing doctor clients
    cannot treat this as an OPD appointment PK.

    use_dashboard_status: admitted rows report status \"scheduled\" so they stay
    visible on GET /appointments/today Scheduled filter. Dedicated IPD APIs
    return the real admission status (admitted | discharged).
    """
    if patient is None:
        patient = get_patient(db, admission.patient_id)

    admitted = admission.admitted_at
    discharged = admission.discharged_at
    age_fields = patient_age_fields(
        patient.date_of_birth if patient else None,
        patient.gender if patient else None,
    )
    uid = admission.admission_no
    raw_status = str(admission.status or "admitted").strip().lower()
    if use_dashboard_status and raw_status == "admitted":
        status = "scheduled"
    else:
        status = raw_status
    return {
        "id": uid,
        "appointment_uid": uid,
        "patient_id": admission.patient_id,
        "patient_name": display_name(patient.first_name, patient.last_name) if patient else "",
        "patient_phone": patient.phone if patient else "",
        "patient_age": age_fields["patient_age"],
        "patient_gender": age_fields["patient_gender"],
        "patient_uid": patient.patient_uid if patient else "",
        "registration_source": registration_source_value(
            getattr(patient, "registration_source", None)
        ),
        "doctor_id": admission.doctor_id,
        "department_id": admission.department_id,
        "scheduled_at": admitted.isoformat() if admitted else None,
        "appointment_date": admitted.date().isoformat() if admitted else None,
        "appointment_time": admitted.strftime("%H:%M:%S") if admitted else None,
        "appointment_type": "ipd",
        "encounter_type": "IPD",
        "admission_id": admission.id,
        "bed_number": admission.bed_number,
        "ward_name": admission.ward_name,
        "status": status,
        "reason": admission.diagnosis,
        "symptoms": None,
        "notes": admission.notes,
        "diagnosis": admission.diagnosis,
        "follow_up": None,
        "admitted_at": admitted.isoformat() if admitted else None,
        "discharged_at": discharged.isoformat() if discharged else None,
        "created_at": admission.created_at.isoformat() if admission.created_at else None,
        "nurse_id": None,
        "nurse_name": None,
    }


def admissions_to_dicts(
    db: Session,
    rows: List[IpdAdmission],
    *,
    use_dashboard_status: bool = False,
) -> List[dict]:
    patient_cache: dict[int, Patient] = {}
    out = []
    for admission in rows:
        pid = admission.patient_id
        if pid not in patient_cache:
            patient_cache[pid] = get_patient(db, pid)
        out.append(
            admission_to_dict(
                db,
                admission,
                patient_cache.get(pid),
                use_dashboard_status=use_dashboard_status,
            )
        )
    return with_nurse_names(db, out)
