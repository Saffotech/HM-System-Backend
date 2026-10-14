"""Lab technician in-app notification helpers (department-scoped)."""
import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.doctor_lab_test_order import LabTestOrder
from Models.lab_test import LabTest
from Models.role import Role
from Models.user import User
from Services import opd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

LAB_TECHNICIAN_ROLE = "lab_technician"


def _active_lab_technician_ids(
    db: Session,
    *,
    department_id: int | None = None,
) -> list[int]:
    query = (
        db.query(User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == LAB_TECHNICIAN_ROLE,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if department_id is not None:
        query = query.filter(User.department_id == department_id)
    rows = query.all()
    return [row[0] for row in rows]


def _lab_tech_ids_for_departments(
    db: Session,
    department_ids: list[int | None],
) -> list[int]:
    seen: set[int] = set()
    queried: set[int | None] = set()
    ids: list[int] = []
    for department_id in department_ids:
        if department_id in queried:
            continue
        queried.add(department_id)
        for tech_id in _active_lab_technician_ids(db, department_id=department_id):
            if tech_id not in seen:
                seen.add(tech_id)
                ids.append(tech_id)
    return ids


def _doctor_display_name(db: Session, doctor_id: int) -> str:
    doctor = db.query(User).filter(User.id == doctor_id).first()
    if not doctor:
        return "Doctor"
    return h.display_name(doctor.first_name, doctor.last_name)


def _actor_display_name(actor: User | None) -> str:
    if not actor:
        return "Admin"
    return h.display_name(actor.first_name, actor.last_name) or "Admin"


def _order_priority(order: LabTestOrder) -> NotificationPriority:
    raw = (order.priority or "").strip().casefold()
    if raw == "urgent":
        return NotificationPriority.HIGH
    return NotificationPriority.NORMAL


def _format_price(value) -> str:
    try:
        return f"{Decimal(str(value)):.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return str(value)


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
    department_id: int | None,
    extra_department_ids: list[int | None] | None = None,
    source_module: SourceModule = SourceModule.LAB,
    reference_type: ReferenceType = ReferenceType.LAB_ORDER,
) -> None:
    department_ids = [department_id]
    if extra_department_ids:
        department_ids.extend(extra_department_ids)
    tech_ids = _lab_tech_ids_for_departments(db, department_ids)
    if not tech_ids:
        logger.info(
            "No active lab technicians in department %s to notify for %s",
            department_id,
            notification_type.value,
        )
        return

    for tech_id in tech_ids:
        try:
            create_notification(
                db,
                user_id=tech_id,
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
        except Exception:
            logger.exception(
                "Failed to notify lab technician %s for %s",
                tech_id,
                notification_type.value,
            )
            try:
                db.rollback()
            except Exception:
                logger.exception(
                    "Failed to rollback after lab notification error for technician %s",
                    tech_id,
                )


def notify_lab_techs_order_created(
    db: Session,
    order: LabTestOrder,
    *,
    doctor_id: int,
    is_repeat: bool = False,
) -> None:
    try:
        doctor_name = _doctor_display_name(db, doctor_id)
        category = order.category or "Laboratory"
        priority_label = order.priority or "normal"
        detail = (
            f"{order.test_name} - {order.patient_name} "
            f"({category}, {priority_label})"
        )
        if is_repeat:
            title = "Repeat lab order"
            message = f"Repeat: {detail}"
        else:
            title = "New lab order"
            message = detail
        _broadcast_to_lab_techs(
            db,
            title=title,
            message=message,
            notification_type=NotificationType.LAB_ORDER_CREATED,
            reference_id=order.id,
            created_by=doctor_id,
            created_by_name=doctor_name,
            priority=_order_priority(order),
            department_id=order.department_id,
        )
    except Exception:
        logger.exception(
            "Failed to notify lab technicians of lab order %s create",
            getattr(order, "id", None),
        )


def notify_lab_techs_order_updated(
    db: Session,
    order: LabTestOrder,
    *,
    doctor_id: int,
    previous_department_id: int | None = None,
    previous_test_name: str | None = None,
) -> None:
    try:
        doctor_name = _doctor_display_name(db, doctor_id)
        category = order.category or "Laboratory"
        priority_label = order.priority or "normal"
        if previous_test_name and previous_test_name != order.test_name:
            test_label = f"{previous_test_name} → {order.test_name}"
        else:
            test_label = order.test_name
        extra_departments: list[int | None] = []
        if (
            previous_department_id is not None
            and previous_department_id != order.department_id
        ):
            extra_departments.append(previous_department_id)
        _broadcast_to_lab_techs(
            db,
            title="Lab order updated",
            message=(
                f"{test_label} - {order.patient_name} "
                f"({category}, {priority_label})"
            ),
            notification_type=NotificationType.LAB_ORDER_CREATED,
            reference_id=order.id,
            created_by=doctor_id,
            created_by_name=doctor_name,
            priority=_order_priority(order),
            department_id=order.department_id,
            extra_department_ids=extra_departments or None,
        )
    except Exception:
        logger.exception(
            "Failed to notify lab technicians of lab order %s update",
            getattr(order, "id", None),
        )


def notify_lab_techs_order_cancelled(
    db: Session,
    order: LabTestOrder,
    *,
    doctor_id: int,
) -> None:
    try:
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
            department_id=order.department_id,
        )
    except Exception:
        logger.exception(
            "Failed to notify lab technicians of lab order %s cancel",
            getattr(order, "id", None),
        )


def notify_lab_techs_catalog_price_changed(
    db: Session,
    test: LabTest,
    *,
    old_price,
    new_price,
    actor: User,
) -> None:
    try:
        actor_name = _actor_display_name(actor)
        message = (
            f"{test.test_name} price changed from ₹{_format_price(old_price)} "
            f"to ₹{_format_price(new_price)}"
        )
        _broadcast_to_lab_techs(
            db,
            title="Lab test price updated",
            message=message,
            notification_type=NotificationType.ADMIN_UPDATE,
            reference_id=test.id,
            created_by=actor.id,
            created_by_name=actor_name,
            priority=NotificationPriority.HIGH,
            department_id=test.department_id,
            source_module=SourceModule.ADMIN,
            # ALERT avoids deep-linking to a lab order id that does not exist.
            reference_type=ReferenceType.ALERT,
        )
    except Exception:
        logger.exception(
            "Failed to notify lab technicians of catalog price change for test %s",
            getattr(test, "id", None),
        )
