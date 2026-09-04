"""Notify the assigned doctor when an IPD patient is admitted to them."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.ipd import IpdAdmission
from Models.patient import Patient
from Models.user import User
from Services import ipd_helpers as h
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)


def _staff_name(db: Session, user_id: Optional[int]) -> str:
    if not user_id:
        return "IPD"
    user = db.query(User).filter(User.id == user_id).first()
    return h.display_name(user.first_name, user.last_name) if user else "IPD"


def _patient_label(db: Session, patient_id: int) -> str:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        return "Patient"
    name = h.display_name(patient.first_name, patient.last_name)
    uid = patient.patient_uid or ""
    return f"{name} ({uid})" if uid else name


def notify_doctor_ipd_admitted(
    db: Session,
    admission: IpdAdmission,
    *,
    created_by: Optional[int] = None,
) -> None:
    """Inbox alert for the assigned doctor. No-op if doctor_id is empty."""
    if not admission.doctor_id:
        return

    patient_name = _patient_label(db, admission.patient_id)
    bed = admission.bed_number or "—"
    ward = admission.ward_name or "—"
    admission_no = admission.admission_no or f"#{admission.id}"
    message = (
        f"IPD patient admitted under you.\n"
        f"Patient: {patient_name}\n"
        f"Admission: {admission_no}\n"
        f"Ward: {ward}  Bed: {bed}"
    )
    try:
        create_notification(
            db,
            user_id=admission.doctor_id,
            title="IPD Patient Admitted",
            message=message,
            notification_type=NotificationType.IPD_ADMITTED,
            source_module=SourceModule.IPD,
            reference_type=ReferenceType.ADMISSION,
            reference_id=admission.id,
            created_by=created_by,
            created_by_name=_staff_name(db, created_by),
            priority=NotificationPriority.HIGH,
        )
    except Exception:
        logger.exception(
            "Failed to notify doctor %s of IPD admission %s",
            admission.doctor_id,
            admission.id,
        )
        db.rollback()


def notify_doctor_ipd_care_team_added(
    db: Session,
    admission: IpdAdmission,
    *,
    doctor_id: int,
    created_by: Optional[int] = None,
) -> None:
    """Inbox alert when a doctor is added to an admission care team."""
    if not doctor_id:
        return

    patient_name = _patient_label(db, admission.patient_id)
    bed = admission.bed_number or "—"
    ward = admission.ward_name or "—"
    admission_no = admission.admission_no or f"#{admission.id}"
    message = (
        f"You were added to an IPD care team.\n"
        f"Patient: {patient_name}\n"
        f"Admission: {admission_no}\n"
        f"Ward: {ward}  Bed: {bed}"
    )
    try:
        create_notification(
            db,
            user_id=doctor_id,
            title="IPD Care Team Assignment",
            message=message,
            notification_type=NotificationType.IPD_ADMITTED,
            source_module=SourceModule.IPD,
            reference_type=ReferenceType.ADMISSION,
            reference_id=admission.id,
            created_by=created_by,
            created_by_name=_staff_name(db, created_by),
            priority=NotificationPriority.HIGH,
        )
    except Exception:
        logger.exception(
            "Failed to notify doctor %s of care-team add on admission %s",
            doctor_id,
            admission.id,
        )
        db.rollback()