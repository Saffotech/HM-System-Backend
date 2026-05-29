from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy.orm import Session
from Models.appointments import Appointment
from Schemas.appointment_schema import AppointmentStatus

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

    return appointments


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

    # ======================================================
    # Valid Workflow Transitions
    # ======================================================

    valid_transitions = {

        "scheduled": [
            "waiting",
            "cancelled"
        ],

        "waiting": [
            "in_progress",
            "cancelled"
        ],

        "in_progress": [
            "completed",
            "cancelled"
        ],

        "completed": [],

        "cancelled": []
    }

    current_status = appointment.status

    # ======================================================
    # Validate Status Transition
    # ======================================================

    if status not in valid_transitions[current_status]:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot change appointment "
                f"status from "
                f"{current_status} to {status}"
            )
        )

    # ======================================================
    # Current Time
    # ======================================================

    current_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    # ======================================================
    # Update Status
    # ======================================================

    appointment.status = status

    # ======================================================
    # Auto Update Timestamps
    # ======================================================

    if status == "waiting":

        appointment.checked_in_at = current_time

    elif status == "in_progress":

        appointment.consultation_started_at = current_time

    elif status == "completed":

        appointment.consultation_completed_at = current_time

    # ======================================================
    # Save Changes
    # ======================================================

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
            Appointment.status == AppointmentStatus.completed
        )
        .order_by(
            Appointment.appointment_date.desc(),
            Appointment.appointment_time.desc()
        )
        .all()
    )

    return appointments


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


# ==========================================================
# Dashboard Stats
# ==========================================================

def get_dashboard_stats_service(
    db: Session,
    doctor_id: int
):

    today_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today()
        )
        .count()
    )

    waiting_patients = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today(),
            Appointment.status == "waiting"
        )
        .count()
    )

    in_progress_patients = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today(),
            Appointment.status == "in_progress"
        )
        .count()
    )

    completed_consultations = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today(),
            Appointment.status == "completed"
        )
        .count()
    )

    cancelled_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today(),
            Appointment.status == "cancelled"
        )
        .count()
    )

    return {

        "today_appointments": today_appointments,

        "patients_waiting": waiting_patients,

        "patients_in_progress": (
            in_progress_patients
        ),

        "completed_consultations": (
            completed_consultations
        ),

        "cancelled_appointments": (
            cancelled_appointments
        )
    }