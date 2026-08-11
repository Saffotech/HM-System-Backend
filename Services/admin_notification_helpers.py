"""Hospital Admin in-app notification helpers (operational alerts broadcast to all active admins)."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.nurse_emergency_alert import EmergencyAlert
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Services import opd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

ADMIN_ROLE = "admin"


def _active_admin_ids(db: Session) -> list[int]:
    rows = (
        db.query(User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == ADMIN_ROLE,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def _staff_name(db: Session, user_id: int | None) -> str:
    if not user_id:
        return "Staff"
    user = db.query(User).filter(User.id == user_id).first()
    return h.display_name(user.first_name, user.last_name) if user else "Staff"


def _patient_label_from_visit(db: Session, visit: OpdVisit) -> str:
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    if not patient:
        return "Patient"
    return h.display_name(patient.first_name, patient.last_name)


def _patient_label_from_alert(db: Session, alert: EmergencyAlert) -> str:
    patient = db.query(Patient).filter(Patient.id == alert.patient_id).first()
    if not patient:
        return "Patient"
    return h.display_name(patient.first_name, patient.last_name)


def _broadcast_to_admins(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: NotificationType,
    source_module: SourceModule,
    reference_type: ReferenceType,
    reference_id: int,
    created_by: Optional[int] = None,
    created_by_name: Optional[str] = None,
    priority: Optional[NotificationPriority] = None,
) -> None:
    admin_ids = _active_admin_ids(db)
    if not admin_ids:
        logger.info("No active hospital admins to notify for %s", notification_type.value)
        return

    for admin_id in admin_ids:
        create_notification(
            db,
            user_id=admin_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=source_module,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=created_by,
            created_by_name=created_by_name,
            priority=priority,
        )


def notify_admins_emergency_alert(
    db: Session,
    alert: EmergencyAlert,
    *,
    created_by: Optional[int] = None,
) -> None:
    patient_name = _patient_label_from_alert(db, alert)
    severity_label = (
        alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    )
    location_parts = [part for part in (alert.ward_name, alert.bed_number) if part]
    message_lines = [f"{severity_label.upper()} — {patient_name}"]
    if location_parts:
        message_lines.append(" — ".join(location_parts))
    if alert.description:
        message_lines.append(alert.description)
    if alert.alert_uid:
        message_lines.append(f"Alert: {alert.alert_uid}")

    _broadcast_to_admins(
        db,
        title=alert.title or "Critical emergency alert",
        message="\n".join(message_lines),
        notification_type=NotificationType.EMERGENCY_ALERT,
        source_module=SourceModule.NURSE,
        reference_type=ReferenceType.ALERT,
        reference_id=alert.id,
        created_by=created_by,
        created_by_name=_staff_name(db, created_by),
        priority=NotificationPriority.CRITICAL,
    )


def notify_admins_queue_enqueue_failed(
    db: Session,
    visit: OpdVisit,
    *,
    reason: str,
    created_by: Optional[int] = None,
) -> None:
    patient_name = _patient_label_from_visit(db, visit)
    message = (
        f"Payment recorded but patient was not added to the doctor queue.\n"
        f"Visit ID: {visit.id}\n"
        f"Patient ID: {visit.patient_id}\n"
        f"Bill: {visit.bill_number}\n"
        f"Patient: {patient_name}\n"
        f"Reason: {reason}"
    )
    _broadcast_to_admins(
        db,
        title="Queue Check-in Failed",
        message=message,
        notification_type=NotificationType.QUEUE_ENQUEUE_FAILED,
        source_module=SourceModule.OPD_BILLING,
        reference_type=ReferenceType.BILL,
        reference_id=visit.id,
        created_by=created_by,
        created_by_name=_staff_name(db, created_by),
        priority=NotificationPriority.HIGH,
    )
