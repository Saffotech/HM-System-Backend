"""Assign / resolve / escalate workflows for nurse emergency alerts."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.nurse_emergency_alert import AlertStatus, AlertSeverity, EmergencyAlert
from Models.patient import Patient
from Models.opd_billing import Appointment
from Models.user import User
from Schemas.nurse_emergency_alert_schema import (
    EmergencyAlertAssign,
    EmergencyAlertResolve,
    EmergencyAlertEscalate,
)
from Enums.notification import (
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Services import nurse_helpers as nh
from Services.nurse_emergency_alert_notify import notify_assigned_nurse_alert
from Services.notification_service import create_notification


def _now():
    return nh.now_ist()


def _get_full_name(user):
    return nh.user_display_name(user)


def assign_alert_service(
    db: Session,
    alert_id: int,
    assign_data: EmergencyAlertAssign,
    nurse_id: int
):

    alert = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.id == alert_id
        )
        .first()
    )

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=400,
            detail="Resolved alert cannot be assigned"
        )

    assigned_nurse_id = (
        assign_data.assigned_nurse_id
        or nurse_id
    )

    nurse = (
        db.query(User)
        .filter(
            User.id == assigned_nurse_id,
            User.is_active == True
        )
        .first()
    )

    if not nurse:
        raise HTTPException(
            status_code=404,
            detail="Nurse not found"
        )

    alert.assigned_nurse_id = (
        assigned_nurse_id
    )

    alert.assigned_at = (
        _now()
    )

    try:

        db.add(alert)

        db.commit()

        db.refresh(alert)

    except Exception as e:

        db.rollback()

        print(
            "ASSIGN ALERT ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to assign alert"
        )

    assigner = db.query(User).filter(User.id == nurse_id).first()
    assigner_name = (
        nh.user_display_name(assigner)
        if assigner
        else "Nurse"
    )
    notify_assigned_nurse_alert(
        db,
        alert,
        nurse_user_id=assigned_nurse_id,
        title=alert.title or "Alert assigned to you",
        created_by=nurse_id,
        created_by_name=assigner_name,
    )

    return {

        "message":
            "Alert assigned successfully",

        "alert_id":
            alert.id,

        "assigned_nurse_id":
            assigned_nurse_id
    }

# ==========================================================
# RESOLVE ALERT
# ==========================================================

def resolve_alert_service(
    db: Session,
    alert_id: int,
    resolve_data: EmergencyAlertResolve,
    nurse_id: int
):

    alert = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.id == alert_id
        )
        .first()
    )

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=400,
            detail="Alert already resolved"
        )

    alert.status = (
        AlertStatus.RESOLVED
    )

    alert.resolved_by = (
        nurse_id
    )

    alert.resolved_at = (
        _now()
    )

    alert.resolution_notes = (
        resolve_data.resolution_notes
    )

    try:

        db.add(alert)

        db.commit()

        db.refresh(alert)

    except Exception as e:

        db.rollback()

        print(
            "RESOLVE ALERT ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to resolve alert"
        )

    return {

        "message":
            "Alert resolved successfully",

        "alert_id":
            alert.id,

        "status":
            alert.status
    }

# ==========================================================
# ESCALATE ALERT
# ==========================================================

def escalate_alert_service(
    db: Session,
    alert_id: int,
    escalate_data: EmergencyAlertEscalate,
    nurse_id: int
):

    alert = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.id == alert_id
        )
        .first()
    )

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found"
        )

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=400,
            detail="Resolved alert cannot be escalated"
        )

    doctor_id = (
        escalate_data.doctor_id
    )

    # ======================================================
    # AUTO DOCTOR LOOKUP
    # ======================================================

    if not doctor_id:

        latest_appointment = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id ==
                alert.patient_id
            )
            .order_by(
                Appointment.created_at.desc()
            )
            .first()
        )

        if not latest_appointment:
            raise HTTPException(
                status_code=404,
                detail="No doctor assigned to patient"
            )

        doctor_id = (
            latest_appointment.doctor_id
        )

    doctor = (
        db.query(User)
        .filter(
            User.id == doctor_id,
            User.is_active == True
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found"
        )

    alert.escalated = True

    alert.escalated_at = (
        _now()
    )

    alert.escalated_to_doctor_id = (
        doctor_id
    )

    alert.escalation_notes = (
        escalate_data.escalation_notes
    )

    try:

        db.add(alert)

        db.commit()

        db.refresh(alert)

    except Exception as e:

        db.rollback()

        print(
            "ESCALATE ALERT ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to escalate alert"
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == alert.patient_id)
        .first()
    )
    patient_name = (
        nh.patient_display_name(patient) or "Patient"
    )
    nurse = db.query(User).filter(User.id == nurse_id).first()
    nurse_name = nh.user_display_name(nurse) or "Nurse"
    location_parts = [part for part in (alert.ward_name, alert.bed_number) if part]
    location = " — ".join(location_parts)
    severity_label = (
        alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
    )
    message_lines = [f"{severity_label.upper()} — {patient_name}"]
    if location:
        message_lines.append(location)
    if escalate_data.escalation_notes:
        message_lines.append(escalate_data.escalation_notes)

    # Critical alerts already notify the doctor when auto-created.
    if alert.severity != AlertSeverity.CRITICAL:
        create_notification(
            db,
            user_id=doctor_id,
            title=alert.title or "Emergency alert escalated",
            message="\n".join(message_lines),
            notification_type=NotificationType.EMERGENCY_ALERT,
            source_module=SourceModule.NURSE,
            reference_type=ReferenceType.PATIENT,
            reference_id=alert.patient_id,
            created_by=nurse_id,
            created_by_name=nurse_name,
        )

    return {

        "message":
            "Alert escalated successfully",

        "alert_id":
            alert.id,

        "doctor_id":
            doctor_id
    }

# ==========================================================
# AUTO ALERT CREATION
# ==========================================================
