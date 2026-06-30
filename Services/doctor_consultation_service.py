from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_lab_test_order import LabTestOrder
from Models.doctor_prescriptions import Prescription
from Models.opd_billing import Appointment, AppointmentStatus
from Schemas.doctor_consultation_schema import SaveConsultationRequest
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Services import doctor_helpers as h
from Services.doctor_appointment_service import get_appointment_by_id_service
from Services.doctor_patient_queue_service import (
    ensure_queue_for_appointment,
    finalize_consultation,
    find_queue_for_appointment_today,
    queue_to_summary,
)
from Services.queue_helpers import persist, status_value


def _appointment_status_value(status) -> str:
    return getattr(status, "value", status)


def _serialize_lab_order(order: LabTestOrder) -> dict:
    return {
        "id": order.id,
        "appointment_id": order.appointment_id,
        "test_name": order.test_name,
        "category": order.category,
        "priority": order.priority,
        "status": status_value(order.status),
        "clinical_notes": order.clinical_notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _serialize_prescription(rx: Prescription) -> dict:
    return {
        "id": rx.id,
        "appointment_id": rx.appointment_id,
        "diagnosis": rx.diagnosis,
        "status": rx.status,
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
    }


def get_consultation_context_service(
    db: Session,
    appointment_id: int,
    doctor_id: int,
) -> dict:
    """Read-only consultation context — no status mutation."""
    appointment = get_appointment_by_id_service(db, appointment_id, doctor_id)
    status = _appointment_status_value(appointment.get("status"))
    if status == AppointmentStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="Cannot open consultation for cancelled appointment")

    queue_row = find_queue_for_appointment_today(db, appointment_id)
    queue = queue_to_summary(queue_row) if queue_row else None

    patient_id = appointment.get("patient_id")
    prescriptions = []
    if patient_id:
        prescriptions = [
            _serialize_prescription(rx)
            for rx in (
                db.query(Prescription)
                .filter(
                    Prescription.doctor_id == doctor_id,
                    Prescription.patient_id == patient_id,
                )
                .order_by(Prescription.created_at.desc())
                .limit(10)
                .all()
            )
        ]

    lab_orders = [
        _serialize_lab_order(order)
        for order in (
            db.query(LabTestOrder)
            .filter(
                LabTestOrder.appointment_id == appointment_id,
                LabTestOrder.doctor_id == doctor_id,
            )
            .order_by(LabTestOrder.created_at.desc())
            .all()
        )
    ]

    return {
        "success": True,
        "appointment": appointment,
        "queue": queue,
        "prescriptions": prescriptions,
        "lab_orders": lab_orders,
    }


def save_consultation_service(
    db: Session,
    payload: SaveConsultationRequest,
    doctor_id: int,
) -> dict:
    """
    Atomic save: ensure queue row, persist clinical data, mark completed everywhere.
    Skips intermediate waiting/in_progress exposure to the client.
    """
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == payload.appointment_id,
            Appointment.doctor_id == doctor_id,
        )
        .with_for_update()
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    status = _appointment_status_value(appointment.status)
    if status == AppointmentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Consultation already completed")
    if status == AppointmentStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="Cannot save consultation for cancelled appointment")

    queue = ensure_queue_for_appointment(
        db,
        payload.appointment_id,
        created_by=doctor_id,
        commit=False,
    )

    finalize_consultation(
        db,
        queue,
        appointment,
        clinical=payload.clinical,
        updated_by=doctor_id,
    )
    persist(db)
    db.refresh(queue)
    db.refresh(appointment)

    appointment_dict = h.appointment_to_dict(db, appointment)
    return {
        "success": True,
        "message": "Consultation saved",
        "appointment": appointment_dict,
        "queue": queue_to_summary(queue),
    }
