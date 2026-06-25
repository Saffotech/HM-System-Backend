from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.opd_billing import Appointment
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Services import doctor_helpers as h

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

    existing = (
        db.query(PatientQueue)
        .filter(PatientQueue.appointment_id == appointment_id)
        .first()
    )
    if existing:
        if existing.status in _ACTIVE_QUEUE_STATUSES:
            if set_appointment_waiting and appointment.status == "scheduled":
                appointment.status = "waiting"
                db.commit()
            db.refresh(existing)
            return existing
        if existing.status == QueueStatus.IN_PROGRESS:
            return existing
        if existing.status in (QueueStatus.COMPLETED, QueueStatus.CANCELLED):
            return reactivate_queue_for_appointment_service(
                db,
                existing,
                appointment,
                set_appointment_waiting=set_appointment_waiting,
            )
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


def _apply_clinical_to_appointment(
    appointment: Appointment,
    clinical: Optional[CompleteConsultationSchema],
) -> None:
    if not appointment or not clinical:
        return
    if clinical.symptoms and clinical.symptoms.strip():
        appointment.reason = clinical.symptoms.strip()
    if clinical.diagnosis and clinical.diagnosis.strip():
        appointment.diagnosis = clinical.diagnosis.strip()
    if clinical.notes and clinical.notes.strip():
        appointment.notes = clinical.notes.strip()
    if clinical.follow_up_date:
        appointment.follow_up_date = clinical.follow_up_date


def complete_consultation_service(
    db: Session,
    queue_id: int,
    doctor_id: int,
    clinical: Optional[CompleteConsultationSchema] = None,
) -> dict:
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
        _apply_clinical_to_appointment(appointment, clinical)
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
