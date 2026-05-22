from datetime import date

from fastapi import HTTPException

from sqlalchemy.orm import Session

from Models.appointments import Appointment


# ==========================================================
# Get Today's Appointments
# ==========================================================

def get_today_appointments_service(

    db: Session,

    doctor_id: int
):

    appointments = (

        db.query(Appointment)

        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today()
        )

        .order_by(
            Appointment.appointment_time.asc()
        )

        .all()
    )

    return {"total appointments" : len(appointments) ,

        "appointments" : appointments}


# ==========================================================
# Get Appointment By ID
# ==========================================================

def get_appointment_by_id_service(

    db: Session,

    appointment_id: int,

    doctor_id: int
):

    appointment = (

        db.query(Appointment)

        .filter(
            Appointment.id == appointment_id,
            Appointment.doctor_id == doctor_id
        )

        .first()
    )

    if not appointment:

        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    return appointment


# ==========================================================
# Update Appointment Status
# ==========================================================

def update_appointment_status_service(

    db: Session,

    appointment_id: int,

    doctor_id: int,

    status: str
):

    valid_status = [
        "scheduled",
        "completed",
        "cancelled",
        "pending"
    ]

    if status not in valid_status:

        raise HTTPException(
            status_code=400,
            detail="Invalid appointment status"
        )

    appointment = (

        db.query(Appointment)

        .filter(
            Appointment.id == appointment_id,
            Appointment.doctor_id == doctor_id
        )

        .first()
    )

    if not appointment:

        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    appointment.status = status

    db.commit()

    db.refresh(appointment)

    return appointment


# ==========================================================
# Appointment History
# ==========================================================

def get_appointment_history_service(

    db: Session,

    doctor_id: int
):

    appointments = (

        db.query(Appointment)

        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date < date.today()
        )

        .order_by(
            Appointment.appointment_date.desc()
        )

        .all()
    )

    return {"total appointments" : len(appointments),
        "appointments" : appointments
            }


# ==========================================================
# Get Appointments By Date
# ==========================================================

def get_appointments_by_date_service(

    db: Session,

    doctor_id: int,

    appointment_date: date
):

    appointments = (

        db.query(Appointment)

        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date
        )

        .order_by(
            Appointment.appointment_time.asc()
        )

        .all()
    )

    return appointments