from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue, QueuePriority, QueueStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.queue_helpers import (
    START_CONSULTATION_ELIGIBLE,
    apply_eligible_queue_filters,
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


def find_queue_for_appointment_today(
    db: Session, appointment_id: int
) -> PatientQueue | None:
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == appointment_id,
            PatientQueue.queue_date == _today(),
        )
        .first()
    )


def _apply_clinical_to_appointment(
    appointment: Appointment | None,
    clinical: CompleteConsultationSchema | None,
) -> None:
    if not appointment or not clinical:
        return
    if clinical.symptoms is not None:
        appointment.symptoms = clinical.symptoms
    if clinical.diagnosis is not None:
        appointment.diagnosis = clinical.diagnosis
    if clinical.notes is not None:
        appointment.notes = clinical.notes
    if clinical.follow_up_date is not None:
        appointment.follow_up_date = clinical.follow_up_date


def queue_to_summary(queue: PatientQueue) -> dict:
    return {
        "id": queue.id,
        "status": status_value(queue.status),
        "appointment_id": queue.appointment_id,
        "token_number": queue.token_number,
    }


def ensure_queue_for_appointment(
    db: Session,
    appointment_id: int,
    *,
    created_by: int | None = None,
    commit: bool = True,
) -> PatientQueue:
    """Return today's queue row for an appointment, creating one if needed."""
    existing = find_queue_for_appointment_today(db, appointment_id)
    if existing:
        if status_value(existing.status) == QueueStatus.COMPLETED.value:
            raise HTTPException(
                status_code=400,
                detail="Consultation already completed for this appointment",
            )
        return existing

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if (
        db.query(PatientQueue)
        .filter(
            PatientQueue.patient_id == appointment.patient_id,
            PatientQueue.doctor_id == appointment.doctor_id,
            PatientQueue.queue_date == _today(),
            PatientQueue.appointment_id != appointment_id,
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
    if commit:
        persist(db)
        db.refresh(queue)
    else:
        db.flush()
    return queue


def finalize_consultation(
    db: Session,
    queue: PatientQueue,
    appointment: Appointment,
    *,
    clinical: CompleteConsultationSchema | None = None,
    updated_by: int | None = None,
) -> dict:
    """Mark queue + appointment completed and persist clinical fields (single flush)."""
    now = datetime.now(IST)

    if not queue.consultation_started_at:
        queue.consultation_started_at = now

    queue.status = QueueStatus.COMPLETED
    queue.consultation_completed_at = now
    if updated_by is not None:
        queue.updated_by = updated_by

    _apply_clinical_to_appointment(appointment, clinical)
    appointment.status = AppointmentStatus.completed

    consultation_minutes = 0.0
    if queue.consultation_started_at:
        consultation_minutes = round(
            (queue.consultation_completed_at - queue.consultation_started_at).total_seconds()
            / 60,
            2,
        )

    return {
        "queue": queue,
        "appointment": appointment,
        "consultation_minutes": consultation_minutes,
    }


def complete_queue_for_appointment_if_exists(
    db: Session,
    appointment_id: int,
    appointment: Appointment,
    *,
    clinical: CompleteConsultationSchema | None = None,
    updated_by: int | None = None,
) -> PatientQueue | None:
    """Complete today's queue row when one exists; do not create a new row."""
    queue = find_queue_for_appointment_today(db, appointment_id)
    if not queue:
        return None
    if status_value(queue.status) == QueueStatus.COMPLETED.value:
        return queue
    finalize_consultation(
        db,
        queue,
        appointment,
        clinical=clinical,
        updated_by=updated_by,
    )
    return queue


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

    if appointment.status == AppointmentStatus.cancelled:
        raise HTTPException(status_code=400, detail="Cannot queue a cancelled appointment")

    visit = (
        db.query(OpdVisit)
        .filter(OpdVisit.appointment_id == appointment_id)
        .order_by(OpdVisit.id.desc())
        .first()
    )
    if not visit or visit.payment_status != "paid":
        raise HTTPException(
            status_code=400,
            detail="Payment must be completed before the patient can join the queue",
        )

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
    q = (
        db.query(PatientQueue)
        .join(Appointment, PatientQueue.appointment_id == Appointment.id)
        .join(OpdVisit, OpdVisit.appointment_id == Appointment.id)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
        )
    )
    q = apply_eligible_queue_filters(q)
    return q.order_by(PatientQueue.priority.desc(), PatientQueue.token_number.asc()).all()


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


def complete_consultation_service(
    db: Session,
    queue_id: int,
    doctor_id: int,
    clinical: CompleteConsultationSchema | None = None,
) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id, PatientQueue.doctor_id == doctor_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    if status_value(queue.status) == QueueStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Consultation already completed")

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    result = finalize_consultation(
        db,
        queue,
        appointment,
        clinical=clinical,
        updated_by=doctor_id,
    )
    persist(db)
    db.refresh(queue)
    return result


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
