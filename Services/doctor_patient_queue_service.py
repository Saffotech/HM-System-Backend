from datetime import date, datetime
from typing import Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.opd_billing import Appointment
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Models.doctor_patient_queue import PatientQueue, QueuePriority, QueueStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.queue_helpers import (
    START_CONSULTATION_ELIGIBLE,
    is_queue_status,
    persist,
    status_value,
)

IST = ZoneInfo("Asia/Kolkata")

_ACTIVE_QUEUE_STATUSES = (
    QueueStatus.WAITING,
    QueueStatus.VITALS_COMPLETED,
)


def reactivate_queue_for_appointment_service(
    db: Session,
    queue: PatientQueue,
    appointment: Appointment,
    *,
    set_appointment_waiting: bool,
) -> PatientQueue:
    """Allow the same appointment to re-enter the queue after completion or reschedule."""
    queue.status = QueueStatus.WAITING
    queue.queue_date = date.today()
    queue.queue_entered_at = datetime.now(IST)
    queue.consultation_started_at = None
    queue.consultation_completed_at = None
    queue.is_current = False
    queue.token_number = generate_token_number_service(db, appointment.doctor_id)
    if set_appointment_waiting:
        appointment.status = "waiting"
    db.commit()
    db.refresh(queue)
    return queue


def _today():
    return opd_helpers.today_ist_date()


def generate_token_number_service(db: Session, doctor_id: int) -> int:
    last_token = (
        db.query(func.max(PatientQueue.token_number))
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
        )
        .scalar()
    )
    return 1 if not last_token else last_token + 1


def add_patient_to_queue_service(
    db: Session, appointment_id: int, *, created_by: int | None = None
) -> PatientQueue:
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if (
        db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == appointment_id,
            PatientQueue.queue_date == _today(),
        )
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Patient already checked in for this appointment today",
        )

    if (
        db.query(PatientQueue)
        .filter(
            PatientQueue.patient_id == appointment.patient_id,
            PatientQueue.doctor_id == appointment.doctor_id,
            PatientQueue.queue_date == _today(),
        )
        .first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Patient already has a queue entry with this doctor today",
        )

    patient = h.get_patient(db, appointment.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    queue = PatientQueue(
        appointment_id=appointment.id,
        patient_id=patient.id,
        patient_name=h.display_name(patient.first_name, patient.last_name),
        patient_uhid=patient.patient_uid,
        patient_phone=patient.phone,
        appointment_uid=appointment.appointment_uid,
        doctor_id=appointment.doctor_id,
        token_number=generate_token_number_service(db, appointment.doctor_id),
        queue_date=_today(),
        status=QueueStatus.WAITING,
        priority=QueuePriority.NORMAL,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(queue)
    appointment.status = AppointmentStatus.waiting
    persist(db)
    db.refresh(queue)
    return queue


def get_today_queue_service(db: Session, doctor_id: int) -> list[PatientQueue]:
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
        )
        .order_by(PatientQueue.priority.desc(), PatientQueue.token_number.asc())
        .all()
    )


def start_consultation_service(db: Session, queue_id: int, doctor_id: int) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id, PatientQueue.doctor_id == doctor_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    status = status_value(queue.status)
    if status == QueueStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Consultation already completed")
    if not is_queue_status(queue.status, START_CONSULTATION_ELIGIBLE):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start consultation when queue status is {status}",
        )
    if queue.consultation_started_at:
        raise HTTPException(status_code=400, detail="Consultation already started")

    now = datetime.now(IST)
    queue.status = QueueStatus.IN_PROGRESS
    queue.consultation_started_at = now

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment:
        appointment.status = AppointmentStatus.in_progress

    waiting_minutes = round((now - queue.queue_entered_at).total_seconds() / 60, 2)
    persist(db)
    db.refresh(queue)
    return {"queue": queue, "waiting_minutes": waiting_minutes}


def complete_consultation_service(db: Session, queue_id: int, doctor_id: int) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id, PatientQueue.doctor_id == doctor_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue.status = QueueStatus.COMPLETED
    queue.consultation_completed_at = datetime.now(IST)

    consultation_minutes = 0.0
    if queue.consultation_started_at:
        consultation_minutes = round(
            (queue.consultation_completed_at - queue.consultation_started_at).total_seconds()
            / 60,
            2,
        )

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment:
        appointment.status = AppointmentStatus.completed

    persist(db)
    db.refresh(queue)
    return {"queue": queue, "consultation_minutes": consultation_minutes}


def get_current_consultation_service(db: Session, doctor_id: int):
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
            PatientQueue.status == QueueStatus.IN_PROGRESS,
        )
        .first()
    )
