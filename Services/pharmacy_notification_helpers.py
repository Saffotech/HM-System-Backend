"""Pharmacist in-app notification helpers (prescription alerts broadcast to all active pharmacists)."""
import logging

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.doctor_prescriptions import Prescription
from Models.role import Role
from Models.user import User
from Services import opd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

PHARMACIST_ROLE = "pharmacist"
DISPENSED_STATUS = "dispensed"


def _active_pharmacist_ids(db: Session) -> list[int]:
    rows = (
        db.query(User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == PHARMACIST_ROLE,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def _doctor_display_name(db: Session, doctor_id: int) -> str:
    doctor = db.query(User).filter(User.id == doctor_id).first()
    if not doctor:
        return "Doctor"
    return h.display_name(doctor.first_name, doctor.last_name)


def _item_count(rx: Prescription) -> int:
    items = getattr(rx, "items", None)
    if items is None:
        return 0
    return len(items)


def _broadcast_to_pharmacists(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: NotificationType,
    reference_id: int,
    created_by: int,
    created_by_name: str,
    priority: NotificationPriority,
) -> None:
    pharmacist_ids = _active_pharmacist_ids(db)
    if not pharmacist_ids:
        logger.info("No active pharmacists to notify for %s", notification_type.value)
        return

    for pharmacist_id in pharmacist_ids:
        create_notification(
            db,
            user_id=pharmacist_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=SourceModule.PHARMACY,
            reference_type=ReferenceType.PRESCRIPTION,
            reference_id=reference_id,
            created_by=created_by,
            created_by_name=created_by_name,
            priority=priority,
        )


def notify_pharmacists_prescription_created(
    db: Session,
    rx: Prescription,
    *,
    doctor_id: int,
) -> None:
    doctor_name = _doctor_display_name(db, doctor_id)
    patient_name = rx.patient_name or "Patient"
    diagnosis = (rx.diagnosis or "").strip() or "Prescription"
    count = _item_count(rx)
    meds_label = f"{count} medicine(s)" if count else "medicines"
    message = f"{patient_name} — {diagnosis} ({meds_label}) by {doctor_name}"
    _broadcast_to_pharmacists(
        db,
        title="New Prescription",
        message=message,
        notification_type=NotificationType.PRESCRIPTION_CREATED,
        reference_id=rx.id,
        created_by=doctor_id,
        created_by_name=doctor_name,
        priority=NotificationPriority.NORMAL,
    )


def notify_pharmacists_prescription_updated(
    db: Session,
    rx: Prescription,
    *,
    doctor_id: int,
) -> None:
    status = (rx.status or "").strip().casefold()
    if status == DISPENSED_STATUS:
        logger.info(
            "Skip PRESCRIPTION_UPDATED for dispensed prescription %s", rx.id
        )
        return

    doctor_name = _doctor_display_name(db, doctor_id)
    patient_name = rx.patient_name or "Patient"
    diagnosis = (rx.diagnosis or "").strip() or "Prescription"
    count = _item_count(rx)
    meds_label = f"{count} medicine(s)" if count else "medicines"
    message = f"{patient_name} — {diagnosis} updated ({meds_label}) by {doctor_name}"
    _broadcast_to_pharmacists(
        db,
        title="Prescription Updated",
        message=message,
        notification_type=NotificationType.PRESCRIPTION_UPDATED,
        reference_id=rx.id,
        created_by=doctor_id,
        created_by_name=doctor_name,
        priority=NotificationPriority.HIGH,
    )
