"""OPD Billing in-app notification helpers."""
import logging
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.opd_billing import Appointment
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Services import opd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

OPD_BILLING_ROLE = "opd_billing"


def _active_opd_billing_ids(db: Session) -> list[int]:
    rows = (
        db.query(User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == OPD_BILLING_ROLE,
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


def _patient_label(db: Session, visit: OpdVisit) -> str:
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    if not patient:
        return "Patient"
    return h.display_name(patient.first_name, patient.last_name)


def _broadcast_to_opd_staff(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: NotificationType,
    reference_type: ReferenceType,
    reference_id: int,
    created_by: Optional[int] = None,
    created_by_name: Optional[str] = None,
    priority: Optional[NotificationPriority] = None,
    exclude_user_id: Optional[int] = None,
) -> None:
    staff_ids = _active_opd_billing_ids(db)
    if exclude_user_id is not None:
        staff_ids = [uid for uid in staff_ids if uid != exclude_user_id]
    if not staff_ids:
        logger.info("No active OPD billing staff to notify for %s", notification_type.value)
        return

    for staff_id in staff_ids:
        create_notification(
            db,
            user_id=staff_id,
            title=title,
            message=message,
            notification_type=notification_type,
            source_module=SourceModule.OPD_BILLING,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=created_by,
            created_by_name=created_by_name,
            priority=priority,
        )


def notify_opd_payment_pending(
    db: Session,
    visit: OpdVisit,
    *,
    created_by: Optional[int] = None,
) -> None:
    if visit.payment_status not in ("pending", "partial"):
        return

    patient_name = _patient_label(db, visit)
    balance = visit.balance_due if visit.balance_due is not None else visit.grand_total
    status_label = "Pay later" if visit.payment_status == "pending" else "Partial payment"
    message = (
        f"{status_label} — collect payment.\n"
        f"Patient: {patient_name}\n"
        f"Bill: {visit.bill_number}\n"
        f"Balance due: ${balance:.2f}"
    )
    _broadcast_to_opd_staff(
        db,
        title="Payment Pending",
        message=message,
        notification_type=NotificationType.PAYMENT_PENDING,
        reference_type=ReferenceType.BILL,
        reference_id=visit.id,
        created_by=created_by,
        created_by_name=_staff_name(db, created_by),
        priority=NotificationPriority.NORMAL,
    )


def notify_opd_enqueue_failed(
    db: Session,
    visit: OpdVisit,
    *,
    reason: str,
    created_by: Optional[int] = None,
) -> None:
    patient_name = _patient_label(db, visit)
    message = (
        f"Payment recorded but patient was not added to the doctor queue.\n"
        f"Visit ID: {visit.id}\n"
        f"Patient ID: {visit.patient_id}\n"
        f"Bill: {visit.bill_number}\n"
        f"Patient: {patient_name}\n"
        f"Reason: {reason}"
    )
    _broadcast_to_opd_staff(
        db,
        title="Queue Check-in Failed",
        message=message,
        notification_type=NotificationType.QUEUE_ENQUEUE_FAILED,
        reference_type=ReferenceType.BILL,
        reference_id=visit.id,
        created_by=created_by,
        created_by_name=_staff_name(db, created_by),
        priority=NotificationPriority.HIGH,
    )


def notify_opd_appointment_no_show(
    db: Session,
    appointment: Appointment,
    *,
    patient_name: str,
    created_by: Optional[int] = None,
) -> None:
    scheduled_label = appointment.scheduled_at.astimezone(h.IST).strftime("%I:%M %p on %d %b")
    message = (
        f"Patient did not attend the scheduled appointment.\n"
        f"Patient: {patient_name}\n"
        f"Appointment: {appointment.appointment_uid}\n"
        f"Scheduled: {scheduled_label}"
    )
    _broadcast_to_opd_staff(
        db,
        title="Appointment No-show",
        message=message,
        notification_type=NotificationType.APPOINTMENT_NO_SHOW,
        reference_type=ReferenceType.APPOINTMENT,
        reference_id=appointment.id,
        created_by=created_by,
        created_by_name=_staff_name(db, created_by),
        priority=NotificationPriority.NORMAL,
    )
