"""Audit logging for doctor-module write actions (Super Admin reads via GET /super-admin/audit)."""
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from Models.user import User
from Schemas.doctor_consultation_schema import SaveConsultationRequest
from Schemas.doctor_ipd_schema import DoctorIpdConsultationSaveRequest
from Schemas.doctor_lab_test_schema import LabTestCreate, LabTestUpdate
from Schemas.doctor_prescription_schema import PrescriptionCreate
from Services.audit_helpers import safe_log_event


def _medicine_count(items) -> int:
    return len(items or [])


def log_consultation_save(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    payload: SaveConsultationRequest,
    result: dict[str, Any],
) -> None:
    prescription = result.get("prescription") or {}
    rx_id = prescription.get("id")
    items = []
    if payload.prescription is not None:
        items = payload.prescription.items
    elif prescription:
        items = prescription.get("items") or []

    safe_log_event(
        db,
        actor=actor,
        action="consultation.save",
        resource_type="appointment",
        resource_id=payload.appointment_id,
        summary=f"Saved OPD consultation for appointment {payload.appointment_id}",
        details={
            "appointment_id": payload.appointment_id,
            "queue_id": (result.get("queue") or {}).get("queue_id"),
            "prescription_id": rx_id,
            "medicine_count": _medicine_count(items),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_consultation_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    appointment_id: int,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="consultation.view",
        resource_type="appointment",
        resource_id=appointment_id,
        summary=f"Viewed consultation context for appointment {appointment_id}",
        details={"appointment_id": appointment_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_ipd_consultation_save(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    payload: DoctorIpdConsultationSaveRequest,
    result: dict[str, Any],
) -> None:
    visit = result.get("visit") or {}
    prescription = result.get("prescription") or {}
    lab_orders = result.get("lab_orders") or []

    safe_log_event(
        db,
        actor=actor,
        action="ipd.consultation.save",
        resource_type="admission",
        resource_id=admission_id,
        summary=f"Saved IPD consultation for admission {admission_id}",
        details={
            "visit_id": visit.get("id"),
            "prescription_id": prescription.get("id"),
            "lab_order_ids": [row.get("id") for row in lab_orders if row.get("id")],
            "medicine_count": _medicine_count(
                payload.prescription.items if payload.prescription else []
            ),
            "lab_count": len(lab_orders),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_prescription_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    payload: PrescriptionCreate,
    prescription_id: int,
) -> None:
    parent_type = "admission" if payload.admission_id is not None else "appointment"
    parent_id = payload.admission_id if payload.admission_id is not None else payload.appointment_id

    safe_log_event(
        db,
        actor=actor,
        action="prescription.create",
        resource_type="prescription",
        resource_id=prescription_id,
        summary=f"Created prescription {prescription_id}",
        details={
            "parent_type": parent_type,
            "parent_id": parent_id,
            "medicine_count": _medicine_count(payload.items),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_prescription_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    prescription_id: int,
    payload: PrescriptionCreate,
) -> None:
    parent_type = "admission" if payload.admission_id is not None else "appointment"
    parent_id = payload.admission_id if payload.admission_id is not None else payload.appointment_id

    safe_log_event(
        db,
        actor=actor,
        action="prescription.update",
        resource_type="prescription",
        resource_id=prescription_id,
        summary=f"Updated prescription {prescription_id}",
        details={
            "parent_type": parent_type,
            "parent_id": parent_id,
            "medicine_count": _medicine_count(payload.items),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_prescription_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    prescription_id: int,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="prescription.view",
        resource_type="prescription",
        resource_id=prescription_id,
        summary=f"Viewed prescription {prescription_id}",
        details={"prescription_id": prescription_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    payload: LabTestCreate,
    order_id: int,
    test_name: str,
) -> None:
    parent_type = "admission" if payload.admission_id is not None else "appointment"
    parent_id = payload.admission_id if payload.admission_id is not None else payload.appointment_id

    safe_log_event(
        db,
        actor=actor,
        action="lab.create",
        resource_type="lab_order",
        resource_id=order_id,
        summary=f"Ordered lab test {test_name!r} (order {order_id})",
        details={
            "parent_type": parent_type,
            "parent_id": parent_id,
            "test_name": test_name,
            "category": payload.category,
            "priority": payload.priority,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    payload: LabTestUpdate,
    test_name: str,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.update",
        resource_type="lab_order",
        resource_id=order_id,
        summary=f"Updated lab order {order_id}",
        details={
            "test_name": test_name,
            "fields": list(payload.model_dump(exclude_unset=True).keys()),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_cancel(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    test_name: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.cancel",
        resource_type="lab_order",
        resource_id=order_id,
        summary=f"Cancelled lab order {order_id}",
        details={"test_name": test_name} if test_name else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_report_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    access_mode: str,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.report.view",
        resource_type="lab_order",
        resource_id=order_id,
        summary=f"Viewed lab report for order {order_id}",
        details={
            "order_id": order_id,
            "access_mode": access_mode,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_appointment_status_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    appointment_id: int,
    new_status: str,
    previous_status: str | None = None,
) -> None:
    action = "appointment.cancel" if new_status == "cancelled" else "appointment.status_update"
    safe_log_event(
        db,
        actor=actor,
        action=action,
        resource_type="appointment",
        resource_id=appointment_id,
        summary=f"Appointment {appointment_id} status -> {new_status}",
        details={
            "previous_status": previous_status,
            "new_status": new_status,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_patient_history_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_uid: str,
    encounter_type: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="patient_history.view",
        resource_type="patient",
        summary=f"Viewed patient history for {patient_uid}",
        details={
            "patient_uid": patient_uid,
            "encounter_type": encounter_type,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_patient_vitals_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="doctor.patient_vitals.view",
        resource_type="patient",
        resource_id=patient_id,
        summary=f"Viewed vitals for patient {patient_id}",
        details={
            "patient_id": patient_id,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_patient_notes_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="doctor.patient_notes.view",
        resource_type="patient",
        resource_id=patient_id,
        summary=f"Viewed nursing notes for patient {patient_id}",
        details={
            "patient_id": patient_id,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_profile_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    fields: list[str],
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="doctor_profile.update",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Doctor {actor.id} updated profile",
        details={"fields": fields},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_profile_image_upload(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="doctor_profile.image_upload",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Doctor {actor.id} uploaded profile image",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_profile_image_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="doctor_profile.image_delete",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Doctor {actor.id} deleted profile image",
        ip_address=ip_address,
        user_agent=user_agent,
    )
