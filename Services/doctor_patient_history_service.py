from datetime import date

from sqlalchemy import extract, or_
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment
from Models.patient import Patient
from Services import doctor_helpers as h


def get_patients_service(
    db: Session,
    doctor_id: int,
    page: int,
    limit: int,
    filter_date: date = None,
    month: int = None,
    year: int = None,
    search: str = None,
) -> dict:
    query = (
        db.query(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed",
            Patient.is_active.is_(True),
        )
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                Patient.phone.ilike(term),
            )
        )

    if filter_date:
        query = query.filter(h.scheduled_on_date(filter_date))
    elif month and year:
        query = query.filter(
            extract("month", Appointment.scheduled_at) == month,
            extract("year", Appointment.scheduled_at) == year,
        )
    elif year:
        query = query.filter(extract("year", Appointment.scheduled_at) == year)

    total_patients = query.count()
    rows = (
        query.order_by(Appointment.scheduled_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total_patients": total_patients,
        "page": page,
        "limit": limit,
        "patients": [h.appointment_to_dict(db, apt, patient) for apt, patient in rows],
    }


def get_patient_details_service(db: Session, doctor_id: int, patient_uhid: str) -> list[dict]:
    rows = (
        db.query(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Patient.patient_uid == patient_uhid,
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed",
            Patient.is_active.is_(True),
        )
        .order_by(Appointment.scheduled_at.desc())
        .all()
    )
    return [h.appointment_to_dict(db, apt, patient) for apt, patient in rows]
