"""Notification helpers for nurse emergency alerts."""
from __future__ import annotations

from sqlalchemy.orm import Session

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Models.nurse_emergency_alert import AlertSeverity, EmergencyAlert
from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.user import User
from Services import nurse_helpers as nh
from Services.notification_service import (
    create_notification,
    notify_nurse_emergency_alert,
)


def alert_severity_priority(severity) -> NotificationPriority:
    value = severity.value if hasattr(severity, "value") else str(severity)
    if value == AlertSeverity.CRITICAL.value:
        return NotificationPriority.CRITICAL
    if value == AlertSeverity.HIGH.value:
        return NotificationPriority.HIGH
    return NotificationPriority.NORMAL


def alert_notify_message(db: Session, alert: EmergencyAlert) -> str:
    patient = (
        db.query(Patient)
        .filter(Patient.id == alert.patient_id)
        .first()
    )
    patient_name = nh.patient_display_name(patient) or "Patient"
    severity_label = (
        alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    )
    message_lines = [f"{severity_label.upper()} — {patient_name}"]
    location_parts = [part for part in (alert.ward_name, alert.bed_number) if part]
    if location_parts:
        message_lines.append(" — ".join(location_parts))
    if alert.description:
        message_lines.append(alert.description)
    return "\n".join(message_lines)


def notify_assigned_nurse_alert(
    db: Session,
    alert: EmergencyAlert,
    *,
    nurse_user_id: int,
    title: str,
    created_by: int | None = None,
    created_by_name: str | None = None,
) -> None:
    if not nurse_user_id:
        return
    notify_nurse_emergency_alert(
        db,
        nurse_user_id=nurse_user_id,
        title=title,
        message=alert_notify_message(db, alert),
        alert_id=alert.id,
        created_by=created_by,
        created_by_name=created_by_name,
        priority=alert_severity_priority(alert.severity),
    )


def doctor_id_for_patient(db: Session, patient_id: int) -> int | None:
    latest_appointment = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.created_at.desc())
        .first()
    )
    return latest_appointment.doctor_id if latest_appointment else None


def notify_doctor_critical_auto_alert(
    db: Session,
    alert: EmergencyAlert,
    *,
    triggered_by: int | None,
) -> None:
    doctor_id = doctor_id_for_patient(db, alert.patient_id)
    if not doctor_id:
        return

    patient = (
        db.query(Patient)
        .filter(Patient.id == alert.patient_id)
        .first()
    )
    patient_name = nh.patient_display_name(patient) or "Patient"
    actor_name = "System"
    created_by = triggered_by
    if triggered_by:
        actor = db.query(User).filter(User.id == triggered_by).first()
        if actor:
            actor_name = nh.user_display_name(actor) or "System"

    severity_label = (
        alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    )
    location_parts = [part for part in (alert.ward_name, alert.bed_number) if part]
    message_lines = [f"{severity_label.upper()} — {patient_name}"]
    if location_parts:
        message_lines.append(" — ".join(location_parts))
    if alert.description:
        message_lines.append(alert.description)

    create_notification(
        db,
        user_id=doctor_id,
        title=alert.title or "Critical emergency alert",
        message="\n".join(message_lines),
        notification_type=NotificationType.EMERGENCY_ALERT,
        source_module=SourceModule.NURSE,
        reference_type=ReferenceType.PATIENT,
        reference_id=alert.patient_id,
        created_by=created_by,
        created_by_name=actor_name,
    )
