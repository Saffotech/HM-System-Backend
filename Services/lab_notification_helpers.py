"""Lab technician in-app notification helpers (order alerts broadcast to all active lab techs)."""
import logging
from typing import Iterable

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.doctor_lab_test_order import LabTestOrder
from Models.role import Role
from Models.user import User
from Services import opd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

LAB_TECHNICIAN_ROLE = "lab_technician"


def _active_lab_technician_ids(db: Session) -> list[int]:
    rows = (
        db.query(User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == LAB_TECHNICIAN_ROLE,
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


def _order_priority(order: LabTestOrder) -> NotificationPriority:
    raw = (order.priority or "").strip().casefold()
    if raw == "urgent":
        return NotificationPriority.HIGH
    return NotificationPriority.NORMAL


def _broadcast_to_lab_techs(
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
    tech_ids = _active_lab_technician_ids(db)
    if not tech_ids:
        logger.info("No active lab technicians to notify for %s", notification_type.value)
        return

    for tech_id in tech_ids:
        create_notification(
            db,
            user_id=tech_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=SourceModule.LAB,
            reference_type=ReferenceType.LAB_ORDER,
            reference_id=reference_id,
            created_by=created_by,
            created_by_name=created_by_name,
            priority=priority,
        )


def notify_lab_techs_order_created(
    db: Session,
    order: LabTestOrder,
    *,
    doctor_id: int,
) -> None:
    doctor_name = _doctor_display_name(db, doctor_id)
    category = order.category or "Laboratory"
    priority_label = order.priority or "normal"
    message = (
        f"{order.test_name} - {order.patient_name} "
        f"({category}, {priority_label})"
    )
    _broadcast_to_lab_techs(
        db,
        title="New lab order",
        message=message,
        notification_type=NotificationType.LAB_ORDER_CREATED,
        reference_id=order.id,
        created_by=doctor_id,
        created_by_name=doctor_name,
        priority=_order_priority(order),
    )


def notify_lab_techs_order_cancelled(
    db: Session,
    order: LabTestOrder,
    *,
    doctor_id: int,
) -> None:
    doctor_name = _doctor_display_name(db, doctor_id)
    message = f"{order.test_name} for {order.patient_name} was cancelled"
    _broadcast_to_lab_techs(
        db,
        title="Lab order cancelled",
        message=message,
        notification_type=NotificationType.LAB_ORDER_CANCELLED,
        reference_id=order.id,
        created_by=doctor_id,
        created_by_name=doctor_name,
        priority=NotificationPriority.HIGH,
    )
