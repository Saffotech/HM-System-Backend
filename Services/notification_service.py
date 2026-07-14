"""Shared notification service — used by OPD, Lab, Nurse, and other modules."""
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.notification import Notification
from Models.user import User
from Services import opd_helpers as h

IST = ZoneInfo("Asia/Kolkata")

DEFAULT_PRIORITY_BY_TYPE: dict[NotificationType, NotificationPriority] = {
    NotificationType.NEW_APPOINTMENT: NotificationPriority.NORMAL,
    NotificationType.LAB_REPORT_READY: NotificationPriority.HIGH,
    NotificationType.APPOINTMENT_CANCELLED: NotificationPriority.HIGH,
    NotificationType.APPOINTMENT_RESCHEDULED: NotificationPriority.HIGH,
    NotificationType.EMERGENCY_ALERT: NotificationPriority.CRITICAL,
    NotificationType.ADMIN_UPDATE: NotificationPriority.HIGH,
    NotificationType.HANDOVER_TAKEN_OVER: NotificationPriority.HIGH,
    NotificationType.SHIFT_UPDATED: NotificationPriority.HIGH,
}


def _now() -> datetime:
    return datetime.now(IST)


def resolve_notification_priority(
    notification_type: NotificationType,
    *,
    priority: Optional[NotificationPriority] = None,
) -> NotificationPriority:
    if priority is not None:
        return priority
    return DEFAULT_PRIORITY_BY_TYPE.get(
        notification_type,
        NotificationPriority.NORMAL,
    )


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    notification_type: NotificationType,
    source_module: SourceModule,
    reference_type: ReferenceType,
    reference_id: int,
    created_by: Optional[int] = None,
    created_by_name: Optional[str] = None,
    priority: Optional[NotificationPriority] = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=resolve_notification_priority(notification_type, priority=priority),
        source_module=source_module,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=created_by,
        created_by_name=created_by_name,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def notify_staff_admin_update(
    db: Session,
    *,
    staff_user_id: int,
    title: str,
    message: str,
    admin_user: User,
    reference_type: ReferenceType = ReferenceType.USER,
    reference_id: Optional[int] = None,
    priority: NotificationPriority = NotificationPriority.HIGH,
    notification_type: NotificationType = NotificationType.ADMIN_UPDATE,
) -> Notification:
    admin_name = h.display_name(admin_user.first_name, admin_user.last_name)
    return create_notification(
        db,
        user_id=staff_user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        source_module=SourceModule.ADMIN,
        reference_type=reference_type,
        reference_id=reference_id if reference_id is not None else staff_user_id,
        created_by=admin_user.id,
        created_by_name=admin_name,
        priority=priority,
    )


def notify_doctor_admin_update(
    db: Session,
    *,
    doctor_user_id: int,
    title: str,
    message: str,
    admin_user: User,
    reference_type: ReferenceType = ReferenceType.USER,
    reference_id: Optional[int] = None,
    priority: NotificationPriority = NotificationPriority.HIGH,
) -> Notification:
    """Backward-compatible alias for doctor admin notifications."""
    return notify_staff_admin_update(
        db,
        staff_user_id=doctor_user_id,
        title=title,
        message=message,
        admin_user=admin_user,
        reference_type=reference_type,
        reference_id=reference_id,
        priority=priority,
        notification_type=NotificationType.ADMIN_UPDATE,
    )


def notify_nurse_emergency_alert(
    db: Session,
    *,
    nurse_user_id: int,
    title: str,
    message: str,
    alert_id: int,
    created_by: Optional[int] = None,
    created_by_name: Optional[str] = None,
    priority: Optional[NotificationPriority] = None,
) -> Notification:
    return create_notification(
        db,
        user_id=nurse_user_id,
        title=title,
        message=message,
        notification_type=NotificationType.EMERGENCY_ALERT,
        source_module=SourceModule.NURSE,
        reference_type=ReferenceType.ALERT,
        reference_id=alert_id,
        created_by=created_by,
        created_by_name=created_by_name,
        priority=priority,
    )


def notify_nurse_handover_taken_over(
    db: Session,
    *,
    outgoing_nurse_id: int,
    title: str,
    message: str,
    handover_id: int,
    created_by: Optional[int] = None,
    created_by_name: Optional[str] = None,
) -> Notification:
    return create_notification(
        db,
        user_id=outgoing_nurse_id,
        title=title,
        message=message,
        notification_type=NotificationType.HANDOVER_TAKEN_OVER,
        source_module=SourceModule.NURSE,
        reference_type=ReferenceType.HANDOVER,
        reference_id=handover_id,
        created_by=created_by,
        created_by_name=created_by_name,
        priority=NotificationPriority.HIGH,
    )


def _priority_sort_key():
    return case(
        (Notification.priority == NotificationPriority.CRITICAL, 0),
        (Notification.priority == NotificationPriority.HIGH, 1),
        else_=2,
    )


def get_notifications(
    db: Session,
    user_id: int,
    *,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    is_read: Optional[bool] = None,
    source_module: Optional[SourceModule] = None,
    notification_type: Optional[NotificationType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    query = db.query(Notification).filter(Notification.user_id == user_id)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    if source_module is not None:
        query = query.filter(Notification.source_module == source_module)
    if notification_type is not None:
        query = query.filter(Notification.notification_type == notification_type)
    if start_date is not None:
        start_dt = datetime.combine(start_date, time.min, tzinfo=IST)
        query = query.filter(Notification.created_at >= start_dt)
    if end_date is not None:
        end_dt = datetime.combine(end_date, time.max, tzinfo=IST)
        query = query.filter(Notification.created_at <= end_dt)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Notification.title.ilike(term),
                Notification.message.ilike(term),
                Notification.created_by_name.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(_priority_sort_key(), Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": rows,
    }


def mark_as_read(db: Session, user_id: int, notification_id: int) -> Notification:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = _now()
        db.commit()
        db.refresh(notification)

    return notification


def mark_all_as_read(db: Session, user_id: int) -> dict:
    updated_at = _now()
    (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .update(
            {"is_read": True, "read_at": updated_at},
            synchronize_session=False,
        )
    )
    db.commit()
    return {"message": "All notifications marked as read"}


def get_unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .count()
    )
