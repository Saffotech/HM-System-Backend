from datetime import date,datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from Models.doctor_patient_queue import PatientQueue
from Models.doctor_appointments import Appointment

# ==========================================================
# Generate Token Number
# ==========================================================

def generate_token_number_service(db: Session,doctor_id: int):

    last_token = (db.query(
            func.max(PatientQueue.token_number)
        ).filter(PatientQueue.doctor_id == doctor_id,
                PatientQueue.queue_date == date.today()
        ).scalar()
    )

    if not last_token:
        return 1

    return last_token + 1

# ==========================================================
# Add Patient To Queue
# ==========================================================

def add_patient_to_queue_service(db: Session,appointment_id: int):

    # ======================================================
    # Fetch Appointment
    # ======================================================

    appointment = (db.query(Appointment)
        .filter(
            Appointment.id == appointment_id
        ).first()
    )

    if not appointment:

        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # ======================================================
    # Check Existing Queue
    # ======================================================

    existing_queue = (db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == appointment_id
        ).first()
    )

    if existing_queue:

        raise HTTPException(
            status_code=400,
            detail="Patient already exists in queue"
        )

    # ======================================================
    # Generate Token Number
    # ======================================================

    token_number = generate_token_number_service(db=db,
        doctor_id=appointment.doctor_id
    )

    # ======================================================
    # Create Queue Entry
    # ======================================================

    queue = PatientQueue(

        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        patient_name=appointment.patient_name,
        patient_uhid=appointment.patient_uhid,
        doctor_id=appointment.doctor_id,
        token_number=token_number,
        queue_date=date.today(),
        status="waiting",
        priority=appointment.priority
    )

    db.add(queue)

    # ======================================================
    # Update Appointment Status
    # ======================================================

    appointment.status = "waiting"
    db.commit()
    db.refresh(queue)

    return queue


# ==========================================================
# Get Today's Queue
# ==========================================================

def get_today_queue_service(db: Session,doctor_id: int):

    queue = (db.query(PatientQueue)
            .filter(PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == date.today()
        ).order_by(PatientQueue.priority.desc(),
                PatientQueue.token_number.asc()
        ).all()
    )

    return queue


# ==========================================================
# Start Consultation
# ==========================================================

def start_consultation_service(
    db: Session,
    queue_id: int,
    doctor_id: int
):

    queue = (db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id,
            PatientQueue.doctor_id == doctor_id
        ).first()
    )

    if not queue:

        raise HTTPException(
            status_code=404,
            detail="Queue not found"
        )

    queue.status = "in_progress"

    queue.consultation_started_at = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    # ======================================================
    # Calculate Waiting Time
    # ======================================================

    waiting_duration = (queue.consultation_started_at -
            queue.queue_entered_at)

    waiting_minutes = round(waiting_duration.total_seconds() / 60,2)

    db.commit()
    db.refresh(queue)

    return {
        "queue": queue,
        "waiting_minutes": waiting_minutes
    }

# ==========================================================
# Complete Consultation
# ==========================================================

def complete_consultation_service(

    db: Session,
    queue_id: int,
    doctor_id: int
):

    queue = (db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id,
            PatientQueue.doctor_id == doctor_id
        ).first()
    )

    if not queue:

        raise HTTPException(
            status_code=404,
            detail="Queue not found"
        )

    queue.status = "completed"

    queue.consultation_completed_at = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    # ======================================================
    # Calculate Consultation Time
    # ======================================================

    consultation_duration = (queue.consultation_completed_at-
        queue.consultation_started_at)

    consultation_minutes = round(consultation_duration.total_seconds() / 60,2)

    # ======================================================
    # Update Appointment Status
    # ======================================================

    appointment = (db.query(Appointment)
        .filter(Appointment.id == queue.appointment_id)
        .first()
    )

    if appointment:
        appointment.status = "completed"

    db.commit()
    db.refresh(queue)

    return {
        "queue": queue,
        "consultation_minutes": consultation_minutes
    }

# ==========================================================
# Get Current Consultation
# ==========================================================

def get_current_consultation_service(db: Session,doctor_id: int):

    queue = (db.query(PatientQueue)
        .filter(PatientQueue.doctor_id == doctor_id,
                PatientQueue.status == "in_progress"
        ).first()
    )

    return queue