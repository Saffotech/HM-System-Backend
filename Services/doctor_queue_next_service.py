from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.doctor_queue_next_request import DoctorQueueNextRequest, NextRequestStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import Patient
from Models.user import User
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.doctor_patient_queue_service import add_patient_to_queue_service
from Services.queue_helpers import (
    READY_FOR_DOCTOR,
    REQUEST_NEXT_APPOINTMENT_STATUSES,
    appointment_status_value,
    is_appointment_status,
    is_queue_status,
    persist,
    status_value,
)

IST = ZoneInfo("Asia/Kolkata")


def _today() -> date:
    return opd_helpers.today_ist_date()


def _request_to_dict(db: Session, req: DoctorQueueNextRequest) -> dict:
    apt = db.query(Appointment).filter(Appointment.id == req.appointment_id).first()
    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
    doctor = db.query(User).filter(User.id == req.doctor_id).first()
    scheduled = apt.scheduled_at if apt else None
    queue = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == req.appointment_id,
            PatientQueue.queue_date == _today(),
        )
        .first()
    )
    resolved_queue_id = req.queue_id or (queue.id if queue else None)
    resolved_queue_number = queue.token_number if queue else None
    if req.queue_id and queue and req.queue_id != queue.id:
        linked = db.query(PatientQueue).filter(PatientQueue.id == req.queue_id).first()
        if linked:
            resolved_queue_number = linked.token_number

    return {
        "request_id": req.id,
        "doctor_id": req.doctor_id,
        "doctor_name": opd_helpers.display_name(
            doctor.first_name, doctor.last_name, prefix="Dr. "
        )
        if doctor
        else None,
        "appointment_id": req.appointment_id,
        "patient_id": req.patient_id,
        "patient_name": h.display_name(patient.first_name, patient.last_name) if patient else None,
        "patient_uid": patient.patient_uid if patient else None,
        "appointment_time": scheduled.strftime("%H:%M:%S") if scheduled else None,
        "queue_id": resolved_queue_id,
        "queue_number": resolved_queue_number,
        "status": status_value(req.status),
        "requested_at": req.requested_at,
    }


def _doctor_has_active_consultation(db: Session, doctor_id: int) -> bool:
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
            PatientQueue.status == QueueStatus.IN_PROGRESS,
        )
        .first()
        is not None
    )


def _next_ready_queue_row(db: Session, doctor_id: int) -> PatientQueue | None:
    return (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == _today(),
            PatientQueue.status.in_(list(READY_FOR_DOCTOR)),
        )
        .order_by(PatientQueue.priority.desc(), PatientQueue.token_number.asc())
        .with_for_update(skip_locked=True)
        .first()
    )


def request_next_patient_service(
    db: Session, doctor_id: int, appointment_id: int | None = None
) -> dict:
    if _doctor_has_active_consultation(db, doctor_id):
        raise HTTPException(
            status_code=400,
            detail="Complete the current consultation before requesting the next patient",
        )

    if appointment_id is None:
        queue = _next_ready_queue_row(db, doctor_id)
        if not queue:
            raise HTTPException(status_code=404, detail="No waiting patients in queue")
        appointment_id = queue.appointment_id

    apt = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.doctor_id == doctor_id)
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found for this doctor")

    if not is_appointment_status(apt.status, REQUEST_NEXT_APPOINTMENT_STATUSES):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request next patient when appointment status is {appointment_status_value(apt.status)}",
        )

    existing_queue = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == appointment_id,
            PatientQueue.queue_date == _today(),
        )
        .with_for_update()
        .first()
    )
    if not existing_queue:
        raise HTTPException(
            status_code=400,
            detail="Patient is not checked in. Reception must check in before next patient request.",
        )
    if not is_queue_status(existing_queue.status, READY_FOR_DOCTOR):
        raise HTTPException(
            status_code=400,
            detail=(
                "Next patient must be waiting or vitals-completed "
                f"(current: {status_value(existing_queue.status)})"
            ),
        )

    today = _today()
    (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.doctor_id == doctor_id,
            DoctorQueueNextRequest.request_date == today,
            DoctorQueueNextRequest.status == NextRequestStatus.pending.value,
        )
        .update(
            {"status": NextRequestStatus.cancelled.value},
            synchronize_session=False,
        )
    )

    req = DoctorQueueNextRequest(
        doctor_id=doctor_id,
        appointment_id=apt.id,
        patient_id=apt.patient_id,
        queue_id=existing_queue.id,
        status=NextRequestStatus.pending.value,
        request_date=today,
        requested_at=datetime.now(IST),
    )
    db.add(req)
    persist(db)
    db.refresh(req)
    return _request_to_dict(db, req)


def list_pending_next_requests_service(
    db: Session, doctor_id: int | None = None
) -> list[dict]:
    today = _today()
    q = db.query(DoctorQueueNextRequest).filter(
        DoctorQueueNextRequest.request_date == today,
        DoctorQueueNextRequest.status == NextRequestStatus.pending.value,
    )
    if doctor_id is not None:
        q = q.filter(DoctorQueueNextRequest.doctor_id == doctor_id)
    rows = q.order_by(DoctorQueueNextRequest.requested_at.asc()).all()
    return [_request_to_dict(db, row) for row in rows]


def fulfill_call_patient(
    db: Session,
    queue_id: int,
    handled_by: int,
    *,
    require_pending_request: bool = True,
) -> PatientQueue:
    """Reception calls patient to doctor room: sets called_at, called_by, and called status."""
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if not is_queue_status(queue.status, READY_FOR_DOCTOR):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot call patient when queue status is {status_value(queue.status)}",
        )

    pending_req = (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.appointment_id == queue.appointment_id,
            DoctorQueueNextRequest.doctor_id == queue.doctor_id,
            DoctorQueueNextRequest.request_date == queue.queue_date,
            DoctorQueueNextRequest.status == NextRequestStatus.pending.value,
        )
        .with_for_update()
        .first()
    )
    if require_pending_request and not pending_req:
        raise HTTPException(
            status_code=400,
            detail="No pending doctor request for this patient. Doctor must click Next patient first.",
        )
    if pending_req and pending_req.queue_id and pending_req.queue_id != queue.id:
        raise HTTPException(
            status_code=400,
            detail="Queue entry does not match the doctor's pending next-patient request",
        )

    other_active = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == queue.doctor_id,
            PatientQueue.queue_date == queue.queue_date,
            PatientQueue.status == QueueStatus.IN_PROGRESS,
            PatientQueue.id != queue.id,
        )
        .first()
    )
    if other_active:
        raise HTTPException(
            status_code=400,
            detail="Doctor already has a patient in consultation",
        )

    now = datetime.now(IST)
    queue.status = QueueStatus.CALLED
    queue.called_at = now
    queue.called_by = handled_by
    queue.updated_by = handled_by

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment and appointment_status_value(appointment.status) == AppointmentStatus.scheduled.value:
        appointment.status = AppointmentStatus.waiting

    if pending_req:
        pending_req.status = NextRequestStatus.fulfilled.value
        pending_req.handled_at = now
        pending_req.handled_by = handled_by

    persist(db)
    db.refresh(queue)
    return queue


def send_in_patient_service(db: Session, appointment_id: int, handled_by: int) -> dict:
    """Deprecated: prefer POST /receptionist/call-patient/{queue_id}."""
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment_status_value(apt.status) in (
        AppointmentStatus.completed.value,
        AppointmentStatus.cancelled.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send in patient when appointment status is {appointment_status_value(apt.status)}",
        )

    existing_queue = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.appointment_id == appointment_id,
            PatientQueue.queue_date == _today(),
        )
        .first()
    )
    if existing_queue and status_value(existing_queue.status) in (
        QueueStatus.CALLED.value,
        QueueStatus.IN_PROGRESS.value,
        QueueStatus.COMPLETED.value,
    ):
        raise HTTPException(
            status_code=400,
            detail="Patient consultation already in progress or completed",
        )

    if existing_queue and is_queue_status(existing_queue.status, READY_FOR_DOCTOR):
        queue = fulfill_call_patient(
            db, existing_queue.id, handled_by, require_pending_request=False
        )
        pending_req = (
            db.query(DoctorQueueNextRequest)
            .filter(
                DoctorQueueNextRequest.appointment_id == appointment_id,
                DoctorQueueNextRequest.status == NextRequestStatus.fulfilled.value,
            )
            .order_by(DoctorQueueNextRequest.handled_at.desc())
            .first()
        )
    else:
        queue = add_patient_to_queue_service(db, appointment_id, created_by=handled_by)
        pending_req = None

    return {
        "success": True,
        "message": "Patient sent in successfully",
        "queue": queue,
        "request": _request_to_dict(db, pending_req) if pending_req else None,
    }
