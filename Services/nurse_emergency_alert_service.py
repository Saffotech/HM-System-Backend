from datetime import datetime,date
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session,aliased
from sqlalchemy import or_
from Models.patient import Patient
from Models.user import User
from Models.opd_billing import Bed

from Models.nurse_emergency_alert import (
    EmergencyAlert,
    AlertStatus,
    AlertSeverity
)

from Schemas.nurse_emergency_alert_schema import (
    EmergencyAlertCreate
)
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_medication_administration import MedicationAdministration
from Models.nurse_medication_administration import (
    MedicationAdministration
)
from Models.opd_billing import Appointment

from Schemas.nurse_emergency_alert_schema import (
    EmergencyAlertAssign,
    EmergencyAlertResolve,
    EmergencyAlertEscalate
)
from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from Services import opd_helpers as h
from Services.notification_service import (
    create_notification,
    notify_nurse_emergency_alert,
)


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


def _alert_severity_priority(severity) -> NotificationPriority:
    value = severity.value if hasattr(severity, "value") else str(severity)
    if value == AlertSeverity.CRITICAL.value:
        return NotificationPriority.CRITICAL
    if value == AlertSeverity.HIGH.value:
        return NotificationPriority.HIGH
    return NotificationPriority.NORMAL


def _alert_notify_message(db: Session, alert: EmergencyAlert) -> str:
    patient = (
        db.query(Patient)
        .filter(Patient.id == alert.patient_id)
        .first()
    )
    patient_name = (
        h.display_name(patient.first_name, patient.last_name)
        if patient
        else "Patient"
    )
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


def _notify_assigned_nurse_alert(
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
        message=_alert_notify_message(db, alert),
        alert_id=alert.id,
        created_by=created_by,
        created_by_name=created_by_name,
        priority=_alert_severity_priority(alert.severity),
    )


def _doctor_id_for_patient(db: Session, patient_id: int) -> int | None:
    latest_appointment = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.created_at.desc())
        .first()
    )
    return latest_appointment.doctor_id if latest_appointment else None


def _notify_doctor_critical_auto_alert(
    db: Session,
    alert: EmergencyAlert,
    *,
    triggered_by: int | None,
) -> None:
    doctor_id = _doctor_id_for_patient(db, alert.patient_id)
    if not doctor_id:
        return

    patient = (
        db.query(Patient)
        .filter(Patient.id == alert.patient_id)
        .first()
    )
    patient_name = (
        h.display_name(patient.first_name, patient.last_name) if patient else "Patient"
    )
    actor_name = "System"
    created_by = triggered_by
    if triggered_by:
        actor = db.query(User).filter(User.id == triggered_by).first()
        if actor:
            actor_name = h.display_name(actor.first_name, actor.last_name)

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


def _generate_alert_uid(
    db: Session
):

    current_year = (
        datetime.now().year
    )

    last_alert = (
        db.query(EmergencyAlert)
        .order_by(
            EmergencyAlert.id.desc()
        )
        .first()
    )

    next_number = 1

    if last_alert:
        next_number = (
            last_alert.id + 1
        )

    return (
        f"EA-{current_year}-"
        f"{str(next_number).zfill(6)}"
    )


def _get_patient_bed_snapshot(
    db: Session,
    patient_id: int
):

    bed = (
        db.query(Bed)
        .filter(
            Bed.patient_id == patient_id,
            Bed.status == "occupied"
        )
        .order_by(
            Bed.admitted_at.desc()
        )
        .first()
    )

    if not bed:
        return {
            "ward_name": None,
            "bed_number": None
        }

    return {

        "ward_name":
            bed.ward_name,

        "bed_number":
            bed.bed_number
    }


def _get_full_name(
    user
):

    if not user:
        return None

    return (
        f"{user.first_name} "
        f"{user.last_name or ''}"
    ).strip()


# ==========================================================
# CREATE ALERT
# ==========================================================

# ==========================================================
# CREATE ALERT
# ==========================================================

def create_alert_service(
    db: Session,
    alert_data: EmergencyAlertCreate,
    nurse_id: int
):

    # ======================================================
    # PATIENT VALIDATION
    # ======================================================

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == alert_data.patient_id,
            Patient.is_active == True
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    # ======================================================
    # BED SNAPSHOT
    # ======================================================

    snapshot = (
        _get_patient_bed_snapshot(
            db,
            patient.id
        )
    )

    # ======================================================
    # CREATE ALERT
    # ======================================================

    alert = EmergencyAlert(

        alert_uid=
            _generate_alert_uid(db),

        patient_id=
            patient.id,

        alert_type=
            alert_data.alert_type,

        severity=
            alert_data.severity,

        title=
            alert_data.title,

        description=
            alert_data.description,

        ward_name=
            snapshot["ward_name"],

        bed_number=
            snapshot["bed_number"],

        status=
            AlertStatus.ACTIVE,

        triggered_by=
            nurse_id,

        triggered_at=
            _now()
    )

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(alert)

        db.commit()

        db.refresh(alert)

    except Exception as e:

        db.rollback()

        print(
            "CREATE ALERT ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to create alert"
        )

    return {

        "message":
            "Emergency alert created successfully",

        "alert_id":
            alert.id,

        "alert_uid":
            alert.alert_uid
    }

# ==========================================================
# DASHBOARD SUMMARY
# ==========================================================

def get_alert_summary_service(
    db: Session
):

    active_total = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.status
            == AlertStatus.ACTIVE
        )
        .count()
    )

    critical_count = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.status
            == AlertStatus.ACTIVE,

            EmergencyAlert.severity
            == AlertSeverity.CRITICAL
        )
        .count()
    )

    high_count = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.status
            == AlertStatus.ACTIVE,

            EmergencyAlert.severity
            == AlertSeverity.HIGH
        )
        .count()
    )

    medium_count = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.status
            == AlertStatus.ACTIVE,

            EmergencyAlert.severity
            == AlertSeverity.MEDIUM
        )
        .count()
    )

    unassigned_count = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.status
            == AlertStatus.ACTIVE,

            EmergencyAlert.assigned_nurse_id.is_(None)
        )
        .count()
    )

    return {

        "active_total":
            active_total,

        "critical_count":
            critical_count,

        "high_count":
            high_count,

        "medium_count":
            medium_count,

        "unassigned_count":
            unassigned_count
    }

# ==========================================================
# ALERT DETAIL
# ==========================================================

def get_alert_detail_service(
    db: Session,
    alert_id: int
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

    # ======================================================
    # PATIENT
    # ======================================================

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == alert.patient_id
        )
        .first()
    )

    patient_name = None
    patient_uid = None

    if patient:

        patient_uid = patient.patient_uid

        patient_name = (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip()

    # ======================================================
    # USERS
    # ======================================================

    triggered_user = None
    assigned_user = None
    resolved_user = None
    escalated_doctor = None

    if alert.triggered_by:

        triggered_user = (
            db.query(User)
            .filter(
                User.id ==
                alert.triggered_by
            )
            .first()
        )

    if alert.assigned_nurse_id:

        assigned_user = (
            db.query(User)
            .filter(
                User.id ==
                alert.assigned_nurse_id
            )
            .first()
        )

    if alert.resolved_by:

        resolved_user = (
            db.query(User)
            .filter(
                User.id ==
                alert.resolved_by
            )
            .first()
        )

    if alert.escalated_to_doctor_id:

        escalated_doctor = (
            db.query(User)
            .filter(
                User.id ==
                alert.escalated_to_doctor_id
            )
            .first()
        )

    # ======================================================
    # LINKED RECORDS
    # ======================================================

    vital_exists = False

    if alert.vital_id:

        vital_exists = (
            db.query(PatientVitals)
            .filter(
                PatientVitals.id ==
                alert.vital_id
            )
            .first()
            is not None
        )

    medication_exists = False

    if alert.medication_administration_id:

        medication_exists = (
            db.query(
                MedicationAdministration
            )
            .filter(
                MedicationAdministration.id ==
                alert.medication_administration_id
            )
            .first()
            is not None
        )

    # ======================================================
    # TIMELINE
    # ======================================================

    timeline = [

        {
            "event": "created",
            "timestamp": alert.triggered_at
        }
    ]

    if alert.assigned_at:

        timeline.append({

            "event": "assigned",

            "timestamp":
                alert.assigned_at
        })

    if alert.escalated_at:

        timeline.append({

            "event": "escalated",

            "timestamp":
                alert.escalated_at
        })

    if alert.resolved_at:

        timeline.append({

            "event": "resolved",

            "timestamp":
                alert.resolved_at
        })

    timeline.sort(
        key=lambda x:
        x["timestamp"]
    )

    # ======================================================
    # RESPONSE
    # ======================================================

    return {

        "id":
            alert.id,

        "alert_uid":
            alert.alert_uid,

        "patient_id":
            alert.patient_id,

        "patient_uid":
            patient_uid,

        "patient_name":
            patient_name,

        "alert_type":
            alert.alert_type,

        "severity":
            alert.severity,

        "title":
            alert.title,

        "description":
            alert.description,

        "ward_name":
            alert.ward_name,

        "bed_number":
            alert.bed_number,

        "status":
            alert.status,

        "triggered_by":
            alert.triggered_by,

        "triggered_by_name":
            _get_full_name(
                triggered_user
            ),

        "triggered_at":
            alert.triggered_at,

        "assigned_nurse_id":
            alert.assigned_nurse_id,

        "assigned_nurse_name":
            _get_full_name(
                assigned_user
            ),

        "resolved_by":
            alert.resolved_by,

        "resolved_by_name":
            _get_full_name(
                resolved_user
            ),

        "resolved_at":
            alert.resolved_at,

        "resolution_notes":
            alert.resolution_notes,

        "escalated":
            alert.escalated,

        "escalated_at":
            alert.escalated_at,

        "escalated_to_doctor_id":
            alert.escalated_to_doctor_id,

        "escalated_doctor_name":
            _get_full_name(
                escalated_doctor
            ),

        "escalation_notes":
            alert.escalation_notes,

        "vital_id":
            alert.vital_id,

        "vital_exists":
            vital_exists,

        "medication_administration_id":
            alert.medication_administration_id,

        "medication_exists":
            medication_exists,

        "created_at":
            alert.created_at,

        "updated_at":
            alert.updated_at,

        "timeline":
            timeline
    }

# ==========================================================
# ASSIGN ALERT
# ==========================================================

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
        h.display_name(assigner.first_name, assigner.last_name)
        if assigner
        else "Nurse"
    )
    _notify_assigned_nurse_alert(
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
        h.display_name(patient.first_name, patient.last_name) if patient else "Patient"
    )
    nurse = db.query(User).filter(User.id == nurse_id).first()
    nurse_name = h.display_name(nurse.first_name, nurse.last_name) if nurse else "Nurse"
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

def create_auto_alert_service(
    db: Session,
    patient_id: int,
    alert_type,
    severity,
    title: str,
    description: str | None = None,
    vital_id: int | None = None,
    medication_administration_id: int | None = None,
    triggered_by: int | None = None
):

    # ======================================================
    # PATIENT VALIDATION
    # ======================================================

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == patient_id,
            Patient.is_active == True
        )
        .first()
    )

    if not patient:
        return None

    # ======================================================
    # PREVENT DUPLICATE ACTIVE ALERTS
    # ======================================================

    existing_alert = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.patient_id == patient_id,
            EmergencyAlert.alert_type == alert_type,
            EmergencyAlert.status == AlertStatus.ACTIVE
        )
        .first()
    )

    if existing_alert:
        return existing_alert

    # ======================================================
    # BED SNAPSHOT
    # ======================================================

    snapshot = (
        _get_patient_bed_snapshot(
            db,
            patient_id
        )
    )

    # ======================================================
    # CREATE ALERT
    # ======================================================

    alert = EmergencyAlert(

        alert_uid=
            _generate_alert_uid(db),

        patient_id=
            patient_id,

        alert_type=
            alert_type,

        severity=
            severity,

        title=
            title,

        description=
            description,

        ward_name=
            snapshot["ward_name"],

        bed_number=
            snapshot["bed_number"],

        status=
            AlertStatus.ACTIVE,

        triggered_by=
            triggered_by,

        triggered_at=
            _now(),

        vital_id=
            vital_id,

        medication_administration_id=
            medication_administration_id
    )

    try:

        db.add(alert)

        db.commit()

        db.refresh(alert)

        if alert.severity == AlertSeverity.CRITICAL:
            _notify_doctor_critical_auto_alert(
                db,
                alert,
                triggered_by=triggered_by,
            )

        # Notify the nurse who triggered a high/critical auto alert
        if (
            triggered_by
            and alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH)
        ):
            actor = db.query(User).filter(User.id == triggered_by).first()
            actor_name = (
                h.display_name(actor.first_name, actor.last_name)
                if actor
                else "System"
            )
            _notify_assigned_nurse_alert(
                db,
                alert,
                nurse_user_id=triggered_by,
                title=alert.title or "Emergency alert raised",
                created_by=triggered_by,
                created_by_name=actor_name,
            )

        return alert

    except Exception as e:

        db.rollback()

        print(
            "AUTO ALERT ERROR:",
            repr(e)
        )

        return None

# ==========================================================
# ALERT LIST
# ==========================================================

def get_alerts_service(
    db: Session,
    status: str | None = "active",
    severity: str | None = None,
    alert_type: str | None = None,
    ward_name: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    assigned_nurse_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20
):

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    AssignedNurse = aliased(User)

    query = (

        db.query(
            EmergencyAlert,
            Patient,
            AssignedNurse
        )

        .join(
            Patient,
            Patient.id ==
            EmergencyAlert.patient_id
        )

        .outerjoin(
            AssignedNurse,
            AssignedNurse.id ==
            EmergencyAlert.assigned_nurse_id
        )
    )

    if status and status.lower() != "all":

        query = query.filter(
            EmergencyAlert.status == status
        )

    if severity:

        query = query.filter(
            EmergencyAlert.severity == severity
        )

    if alert_type:

        query = query.filter(
            EmergencyAlert.alert_type == alert_type
        )

    if ward_name:

        query = query.filter(
            EmergencyAlert.ward_name.ilike(
                f"%{ward_name}%"
            )
        )

    if patient_id:

        query = query.filter(
            EmergencyAlert.patient_id == patient_id
        )

    if patient_uid:

        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid.strip()}%"
            )
        )

    if assigned_nurse_id:

        query = query.filter(
            EmergencyAlert.assigned_nurse_id ==
            assigned_nurse_id
        )

    if from_date:

        query = query.filter(
            EmergencyAlert.triggered_at >= from_date
        )

    if to_date:

        query = query.filter(
            EmergencyAlert.triggered_at <= to_date
        )

    if search:

        query = query.filter(

            or_(

                EmergencyAlert.alert_uid.ilike(
                    f"%{search}%"
                ),

                EmergencyAlert.title.ilike(
                    f"%{search}%"
                ),

                Patient.patient_uid.ilike(
                    f"%{search}%"
                ),

                Patient.first_name.ilike(
                    f"%{search}%"
                ),

                Patient.last_name.ilike(
                    f"%{search}%"
                )
            )
        )

    total = query.count()

    records = (

        query

        .order_by(
            EmergencyAlert.triggered_at.desc()
        )

        .offset(
            (page - 1) * limit
        )

        .limit(limit)

        .all()
    )

    data = []

    for alert, patient, nurse in records:

        patient_name = (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip()

        assigned_nurse_name = (
            _get_full_name(nurse)
            if nurse else None
        )

        data.append({

            "id": alert.id,
            "alert_uid": alert.alert_uid,

            "patient_id": patient.id,
            "patient_uid": patient.patient_uid,
            "patient_name": patient_name,

            "alert_type": alert.alert_type,
            "severity": alert.severity,

            "title": alert.title,

            "ward_name": alert.ward_name,
            "bed_number": alert.bed_number,

            "status": alert.status,

            "assigned_nurse_id":
                alert.assigned_nurse_id,

            "assigned_nurse_name":
                assigned_nurse_name,

            "escalated":
                alert.escalated,

            "triggered_at":
                alert.triggered_at,

            "created_at":
                alert.created_at,

            "updated_at":
                alert.updated_at
        })

    return {

        "total": total,

        "page": page,

        "limit": limit,

        "data": data
    }



