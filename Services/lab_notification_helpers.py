"""Helpers to notify lab technicians about doctor lab orders."""
from typing import Optional

from sqlalchemy.orm import Session, joinedload

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

LAB_TECHNICIAN_ROLE = "lab_technician"


def _active_lab_technician_ids(db: Session) -> list[int]:
    rows = (
        db.query(User.id)
        .join(Role, Role.id == User.role_id)
        .filter(
            Role.name == LAB_TECHNICIAN_ROLE,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def _doctor_display_name(db: Session, doctor_id: int) -> str:
    doctor = (
        db.query(User)
        .options(joinedload(User.role_obj))
        .filter(User.id == doctor_id)
        .first()
    )
    if not doctor:
        return "Doctor"
    return h.display_name(doctor.first_name, doctor.last_name)


def notify_lab_technicians_of_order(
    db: Session,
    order: LabTestOrder,
    *,
    notification_type: NotificationType,
    title: str,
    message: str,
    created_by: int,
    priority: Optional[NotificationPriority] = None,
) -> int:
    """
    Create one inbox notification per active lab technician.
    Returns number of notifications created.
    """
    tech_ids = _active_lab_technician_ids(db)
    if not tech_ids:
        return 0

    created_by_name = _doctor_display_name(db, created_by)
    count = 0
    for tech_id in tech_ids:
        create_notification(
            db,
            user_id=tech_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=SourceModule.LAB,
            reference_type=ReferenceType.LAB_ORDER,
            reference_id=order.id,
            created_by=created_by,
            created_by_name=created_by_name,
            priority=priority,
        )
        count += 1
    return count


def notify_lab_order_created(db: Session, order: LabTestOrder, doctor_id: int) -> int:
    priority = None
    if (order.priority or "").strip().lower() == "urgent":
        priority = NotificationPriority.HIGH

    return notify_lab_technicians_of_order(
        db,
        order,
        notification_type=NotificationType.LAB_ORDER_CREATED,
        title="New lab order",
        message=(
            f"{order.test_name} — {order.patient_name} "
            f"({order.category}, {order.priority})"
        ),
        created_by=doctor_id,
        priority=priority,
    )


def notify_lab_order_cancelled(db: Session, order: LabTestOrder, doctor_id: int) -> int:
    return notify_lab_technicians_of_order(
        db,
        order,
        notification_type=NotificationType.LAB_ORDER_CANCELLED,
        title="Lab order cancelled",
        message=f"{order.test_name} for {order.patient_name} was cancelled",
        created_by=doctor_id,
        priority=NotificationPriority.HIGH,
    )
