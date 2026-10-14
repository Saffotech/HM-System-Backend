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


def notify_nurses_ipd_bed_patient(
    db: Session,
    admission: IpdAdmission,
    *,
    created_by: Optional[int] = None,
    bed_id: Optional[int] = None,
    exclude_user_ids: Optional[set[int]] = None,
    title: str = "Patient assigned to your bed",
    intro: str = "A patient was assigned to your allocated bed.",
) -> None:
    """Inbox alert for nurses allocated to the patient's bed. No-op if none."""
    target_bed_id = bed_id if bed_id is not None else admission.bed_id
    nurse_ids = h.allocated_nurse_ids_for_bed(db, target_bed_id)
    skip = {uid for uid in (exclude_user_ids or set()) if uid}

    patient_name = _patient_label(db, admission.patient_id)
    bed = admission.bed_number or "—"
    ward = admission.ward_name or "—"
    admission_no = admission.admission_no or f"#{admission.id}"
    message = (
        f"{intro}\n"
        f"Patient: {patient_name}\n"
        f"Admission: {admission_no}\n"
        f"Ward: {ward}  Bed: {bed}"
    )

    for nurse_id in nurse_ids:
        if nurse_id in skip:
            continue
        try:
            create_notification(
                db,
                user_id=nurse_id,
                title=title,
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
                "Failed to notify nurse %s of IPD admission %s on bed %s",
                nurse_id,
                admission.id,
                target_bed_id,
            )
            db.rollback()


def _notify_doctor_care_team(
    db: Session,
    admission: IpdAdmission,
    *,
    user_id: int,
    title: str,
    intro: str,
    created_by: Optional[int] = None,
    extra_line: Optional[str] = None,
    log_action: str = "care-team update",
) -> None:
    """Send one IPD care-team inbox row. No-op if user_id is empty."""
    if not user_id:
        return

    patient_name = _patient_label(db, admission.patient_id)
    bed = admission.bed_number or "—"
    ward = admission.ward_name or "—"
    admission_no = admission.admission_no or f"#{admission.id}"
    lines = [intro]
    if extra_line:
        lines.append(extra_line)
    lines.extend(
        [
            f"Patient: {patient_name}",
            f"Admission: {admission_no}",
            f"Ward: {ward}  Bed: {bed}",
        ]
    )
    try:
        create_notification(
            db,
            user_id=user_id,
            title=title,
            message="\n".join(lines),
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
            "Failed to notify doctor %s of %s on admission %s",
            user_id,
            log_action,
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
    """Inbox alert for the doctor being added to an admission care team."""
    _notify_doctor_care_team(
        db,
        admission,
        user_id=doctor_id,
        title="IPD Care Team Assignment",
        intro="You were added to an IPD care team.",
        created_by=created_by,
        log_action="care-team add",
    )


def notify_doctors_ipd_care_team_added(
    db: Session,
    admission: IpdAdmission,
    *,
    associated_doctor_id: int,
    created_by: Optional[int] = None,
) -> None:
    """Notify the new associated doctor and the primary attending doctor."""
    notify_doctor_ipd_care_team_added(
        db, admission, doctor_id=associated_doctor_id, created_by=created_by
    )
    primary_id = admission.doctor_id
    if not primary_id or int(primary_id) == int(associated_doctor_id):
        return
    doctor_name = h.doctor_display(db, associated_doctor_id) or "A doctor"
    _notify_doctor_care_team(
        db,
        admission,
        user_id=primary_id,
        title="IPD Care Team Updated",
        intro="A doctor was added to your patient's care team.",
        extra_line=f"Doctor: {doctor_name}",
        created_by=created_by,
        log_action="care-team add (primary)",
    )


def notify_doctors_ipd_care_team_removed(
    db: Session,
    admission: IpdAdmission,
    *,
    associated_doctor_id: int,
    created_by: Optional[int] = None,
) -> None:
    """Notify the removed associated doctor and the primary attending doctor."""
    _notify_doctor_care_team(
        db,
        admission,
        user_id=associated_doctor_id,
        title="Removed from IPD Care Team",
        intro="You were removed from an IPD care team.",
        created_by=created_by,
        log_action="care-team remove",
    )
    primary_id = admission.doctor_id
    if not primary_id or int(primary_id) == int(associated_doctor_id):
        return
    doctor_name = h.doctor_display(db, associated_doctor_id) or "A doctor"
    _notify_doctor_care_team(
        db,
        admission,
        user_id=primary_id,
        title="IPD Care Team Updated",
        intro="A doctor was removed from your patient's care team.",
        extra_line=f"Doctor: {doctor_name}",
        created_by=created_by,
        log_action="care-team remove (primary)",
    )