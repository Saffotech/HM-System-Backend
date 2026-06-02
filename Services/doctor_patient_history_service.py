from datetime import date
from sqlalchemy import (extract,or_)
from sqlalchemy.orm import Session
from Models.doctor_appointments import Appointment

# ==========================================================
# Get Patients Service
# ==========================================================

def get_patients_service(

    db: Session,
    doctor_id: int,
    page: int,
    limit: int,
    filter_date: date = None,
    month: int = None,
    year: int = None,
    search: str = None
):

    query = (db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed"
        )
    )

    # ======================================================
    # Search Filter
    # ======================================================

    if search:
        query = query.filter(
            or_(
                Appointment.patient_name.ilike(
                    f"%{search}%"
                ),
        Appointment.patient_uhid.ilike(
                    f"%{search}%"
                ),
                Appointment.patient_phone.ilike(
                    f"%{search}%"
                )
            )
        )

    # ======================================================
    # Date Filter
    # ======================================================

    if filter_date:

        query = query.filter(Appointment.appointment_date == filter_date)

    # ======================================================
    # Month + Year Filter
    # ======================================================

    elif month and year:

        query = query.filter(extract("month",
                Appointment.appointment_date
            ) == month,
        extract("year",Appointment.appointment_date) == year
        )

    # ======================================================
    # Year Filter
    # ======================================================

    elif year:

        query = query.filter(extract("year",
                Appointment.appointment_date) == year
        )

    # ======================================================
    # Total Patients Count
    # ======================================================

    total_patients = query.count()

    # ======================================================
    # Pagination
    # ======================================================

    patients = (query.order_by(
            Appointment.appointment_date.desc()
        ).offset(
            (page - 1) * limit
        ).limit(limit).all()
    )

    return {
        "total_patients": total_patients,
        "page": page,
        "limit": limit,
        "patients": patients
    }


# ==========================================================
# Get Patient Details Service
# ==========================================================

def get_patient_details_service(

    db: Session,
    doctor_id: int,
    patient_uhid: str
):

    patient = (db.query(Appointment)
        .filter(
    Appointment.patient_uhid == patient_uhid,
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed"
        ).order_by(
            Appointment.appointment_date.desc()
        ).all()
    )

    return patient