from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue
from Models.opd_billing import Appointment
from Services import doctor_helpers as h

IST = ZoneInfo("Asia/Kolkata")


def generate_token_number_service(db: Session, doctor_id: int) -> int:
    last_token = (
        db.query(func.max(PatientQueue.token_number))
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == date.today(),
        )
        .scalar()
    )
    return 1 if not last_token else last_token + 1


def add_patient_to_queue_service(db: Session, appointment_id: int) -> PatientQueue:
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if db.query(PatientQueue).filter(PatientQueue.appointment_id == appointment_id).first():
        raise HTTPException(status_code=400, detail="Patient already exists in queue")

    patient = h.get_patient(db, appointment.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    queue = PatientQueue(
        appointment_id=appointment.id,
        patient_id=patient.id,
        patient_name=h.display_name(patient.first_name, patient.last_name),
        patient_uhid=patient.patient_uid,
        doctor_id=appointment.doctor_id,
        token_number=generate_token_number_service(db, appointment.doctor_id),
        queue_date=date.today(),
        status="waiting",
        priority="normal",
    )
    db.add(queue)
    appointment.status = "waiting"
    db.commit()
    db.refresh(queue)
    return queue


def get_today_queue_service(db: Session, doctor_id: int) -> list[PatientQueue]:
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == date.today(),
        )
        .order_by(PatientQueue.priority.desc(), PatientQueue.token_number.asc())
        .all()
    )


def start_consultation_service(db: Session, queue_id: int, doctor_id: int) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id, PatientQueue.doctor_id == doctor_id)
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue.status = "in_progress"
    queue.consultation_started_at = datetime.now(IST)

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment:
        appointment.status = "in_progress"

    waiting_minutes = round(
        (queue.consultation_started_at - queue.queue_entered_at).total_seconds() / 60,
        2,
    )
    db.commit()
    db.refresh(queue)
    return {"queue": queue, "waiting_minutes": waiting_minutes}


def complete_consultation_service(db: Session, queue_id: int, doctor_id: int) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id, PatientQueue.doctor_id == doctor_id)
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue.status = "completed"
    queue.consultation_completed_at = datetime.now(IST)

    consultation_minutes = 0.0
    if queue.consultation_started_at:
        consultation_minutes = round(
            (queue.consultation_completed_at - queue.consultation_started_at).total_seconds() / 60,
            2,
        )

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment:
        appointment.status = "completed"

    db.commit()
    db.refresh(queue)
    return {"queue": queue, "consultation_minutes": consultation_minutes}


def get_current_consultation_service(db: Session, doctor_id: int):
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.status == "in_progress",
        )
        .first()
    )
