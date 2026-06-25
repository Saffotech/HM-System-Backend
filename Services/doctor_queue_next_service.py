from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from Models.doctor_patient_queue import PatientQueue
from Models.doctor_queue_next_request import DoctorQueueNextRequest
from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.user import User
from Services import doctor_helpers as h
from Services.opd_helpers import display_name as opd_display_name
from Services.doctor_patient_queue_service import add_patient_to_queue_service

IST = ZoneInfo("Asia/Kolkata")


def _request_to_dict(db: Session, req: DoctorQueueNextRequest) -> dict:
    apt = db.query(Appointment).filter(Appointment.id == req.appointment_id).first()
    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
    doctor = db.query(User).filter(User.id == req.doctor_id).first()
    scheduled = apt.scheduled_at if apt else None
    return {
        "id": req.id,
        "doctor_id": req.doctor_id,
        "doctor_name": opd_display_name(doctor.first_name, doctor.last_name, prefix="Dr. ")
        if doctor
        else None,
        "appointment_id": req.appointment_id,
        "patient_id": req.patient_id,
        "patient_name": h.display_name(patient.first_name, patient.last_name) if patient else None,
        "patient_uid": patient.patient_uid if patient else None,
        "appointment_time": scheduled.strftime("%H:%M:%S") if scheduled else None,
        "status": req.status,
        "requested_at": req.requested_at,
    }


def request_next_patient_service(db: Session, doctor_id: int, appointment_id: int) -> dict:
    apt = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.doctor_id == doctor_id)
        .first()
    )
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found for this doctor")

    if apt.status not in ("scheduled", "waiting"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request next patient when appointment status is {apt.status}",
        )

    today = date.today()
    (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.doctor_id == doctor_id,
            DoctorQueueNextRequest.request_date == today,
            DoctorQueueNextRequest.status == "pending",
        )
        .update({"status": "cancelled"}, synchronize_session=False)
    )

    req = DoctorQueueNextRequest(
        doctor_id=doctor_id,
        appointment_id=apt.id,
        patient_id=apt.patient_id,
        status="pending",
        request_date=today,
        requested_at=datetime.now(IST),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _request_to_dict(db, req)


def list_pending_next_requests_service(db: Session) -> list[dict]:
    today = date.today()
    rows = (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.request_date == today,
            DoctorQueueNextRequest.status == "pending",
        )
        .order_by(DoctorQueueNextRequest.requested_at.asc())
        .all()
    )
    return [_request_to_dict(db, row) for row in rows]


def send_in_patient_service(db: Session, appointment_id: int, handled_by: int) -> dict:
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if apt.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send in patient when appointment status is {apt.status}",
        )

    existing_queue = (
        db.query(PatientQueue).filter(PatientQueue.appointment_id == appointment_id).first()
    )
    if existing_queue and existing_queue.status in ("in_progress", "completed"):
        raise HTTPException(
            status_code=400,
            detail="Patient consultation already in progress or completed",
        )

    if existing_queue and existing_queue.status == "waiting":
        queue = existing_queue
        if apt.status != "waiting":
            apt.status = "waiting"
    else:
        queue = add_patient_to_queue_service(db, appointment_id)

    now = datetime.now(IST)
    pending_req = (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.appointment_id == appointment_id,
            DoctorQueueNextRequest.status == "pending",
        )
        .first()
    )
    if pending_req:
        pending_req.status = "fulfilled"
        pending_req.handled_at = now
        pending_req.handled_by = handled_by

    other_pending = (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.doctor_id == apt.doctor_id,
            DoctorQueueNextRequest.request_date == date.today(),
            DoctorQueueNextRequest.status == "pending",
            DoctorQueueNextRequest.id != (pending_req.id if pending_req else -1),
        )
        .all()
    )
    for row in other_pending:
        row.status = "cancelled"

    db.commit()
    db.refresh(queue)

    return {
        "success": True,
        "message": "Patient sent in successfully",
        "queue": queue,
        "request": _request_to_dict(db, pending_req) if pending_req else None,
    }
