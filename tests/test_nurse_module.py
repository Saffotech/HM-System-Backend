"""Service-level tests for nurse overview, dashboard stats, handover take-over, alerts, notifications."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return compiler.visit_JSON(JSON())


from Enums.notification import NotificationType, ReferenceType, SourceModule
from Models.department import Department
from Models.doctor_patient_queue import PatientQueue, QueuePriority, QueueStatus
from Models.doctor_profile import DoctorProfile  # noqa: F401 — User.doctor_profile
from Models.nurse_emergency_alert import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    EmergencyAlert,
)
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals, VitalStatus
from Models.nurse_profile import NurseProfile  # noqa: F401 — User.nurse_profile
from Models.nurse_shift_handover import (
    HandoverStatus,
    ShiftHandover,
    ShiftHandoverPatient,
)
from Models.notification import Notification
from Models.opd_billing import Appointment, AppointmentStatus, Bed
from Models.patient import Patient
from Models.role import Role
from Models.user import User
from Schemas.nurse_emergency_alert_schema import EmergencyAlertAssign
from Schemas.nurse_shift_handover_schema import ShiftHandoverTakeOver
from Services.nurse_dashboard_service import get_nurse_dashboard_stats_service
from Services.nurse_emergency_alert_service import assign_alert_service
from Services.nurse_patient_overview_service import get_nurse_patient_overview_service
from Services.nurse_shift_handover_service import take_over_handover_service
from Services.notification_service import (
    create_notification,
    get_unread_count,
    mark_as_read,
)


IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def nurse_seed(db):
    dept = Department(name="General", code="GEN")
    db.add(dept)
    db.flush()

    nurse_role = Role(name="nurse", description="Nursing staff")
    doctor_role = Role(name="doctor", description="Doctor")
    db.add_all([nurse_role, doctor_role])
    db.flush()

    nurse_a = User(
        first_name="Priya",
        last_name="Sharma",
        email="nurse_a@test.com",
        password="hashed",
        role_id=nurse_role.id,
        department_id=dept.id,
        is_active=True,
    )
    nurse_b = User(
        first_name="Anita",
        last_name="Verma",
        email="nurse_b@test.com",
        password="hashed",
        role_id=nurse_role.id,
        department_id=dept.id,
        is_active=True,
    )
    doctor = User(
        first_name="Ravi",
        last_name="Doc",
        email="doctor@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept.id,
        is_active=True,
    )
    db.add_all([nurse_a, nurse_b, doctor])
    db.flush()

    patient = Patient(
        patient_uid="P-N-1001",
        first_name="Ramesh",
        last_name="Patil",
        phone="9876543210",
        allergies="Penicillin",
        is_active=True,
    )
    db.add(patient)
    db.flush()

    bed = Bed(
        bed_number="B-12",
        ward_name="Ward A",
        status="occupied",
        patient_id=patient.id,
        department_id=dept.id,
        admitted_at=datetime.now(IST),
    )
    db.add(bed)
    db.flush()

    appointment = Appointment(
        appointment_uid="APT-N-001",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=datetime.now(IST),
        status=AppointmentStatus.scheduled,
    )
    db.add(appointment)
    db.flush()

    db.commit()
    return {
        "dept": dept,
        "nurse_a": nurse_a,
        "nurse_b": nurse_b,
        "doctor": doctor,
        "patient": patient,
        "bed": bed,
        "appointment": appointment,
        "nurse_role": nurse_role,
    }


def test_patient_overview_composes_clinical_data(db, nurse_seed):
    patient = nurse_seed["patient"]
    nurse = nurse_seed["nurse_a"]

    vital = PatientVitals(
        patient_id=patient.id,
        recorded_by=nurse.id,
        temperature=98.6,
        blood_pressure="120/80",
        heart_rate=72,
        oxygen_saturation=98,
        status=VitalStatus.RECORDED,
        recorded_at=datetime.now(IST),
    )
    note = NursingNote(
        patient_id=patient.id,
        nurse_id=nurse.id,
        symptoms="Mild fever",
        additional_notes="Stable",
    )
    alert = EmergencyAlert(
        alert_uid="EA-2026-000001",
        patient_id=patient.id,
        alert_type=AlertType.HIGH_FEVER,
        severity=AlertSeverity.HIGH,
        title="Fever alert",
        status=AlertStatus.ACTIVE,
        is_active=True,
        ward_name="Ward A",
        bed_number="B-12",
        triggered_by=nurse.id,
    )
    db.add_all([vital, note, alert])
    db.commit()

    overview = get_nurse_patient_overview_service(db, patient.id)

    assert overview["success"] is True
    assert overview["patient"]["patient_uid"] == "P-N-1001"
    assert overview["bed"]["bed_number"] == "B-12"
    assert overview["last_vitals"]["temperature"] == 98.6
    assert len(overview["recent_notes"]) == 1
    assert overview["recent_notes"][0]["symptoms"] == "Mild fever"
    assert len(overview["active_alerts"]) == 1
    assert overview["active_alerts"][0]["alert_uid"] == "EA-2026-000001"


def test_patient_overview_not_found(db):
    with pytest.raises(HTTPException) as exc:
        get_nurse_patient_overview_service(db, 99999)
    assert exc.value.status_code == 404


def test_dashboard_stats_counts(db, nurse_seed):
    patient = nurse_seed["patient"]
    nurse = nurse_seed["nurse_a"]
    doctor = nurse_seed["doctor"]
    appointment = nurse_seed["appointment"]

    db.add(
        PatientQueue(
            appointment_id=appointment.id,
            patient_id=patient.id,
            patient_name="Ramesh Patil",
            patient_uhid=patient.patient_uid,
            patient_phone=patient.phone,
            appointment_uid=appointment.appointment_uid,
            doctor_id=doctor.id,
            token_number=1,
            queue_date=date.today(),
            status=QueueStatus.SCHEDULED,
            priority=QueuePriority.NORMAL,
        )
    )
    db.add(
        EmergencyAlert(
            alert_uid="EA-2026-000002",
            patient_id=patient.id,
            alert_type=AlertType.LOW_SPO2,
            severity=AlertSeverity.CRITICAL,
            title="Low SpO2",
            status=AlertStatus.ACTIVE,
            is_active=True,
            triggered_by=nurse.id,
        )
    )
    db.add(
        ShiftHandover(
            handover_uid="HO-2026-000001",
            outgoing_nurse_id=nurse.id,
            ward_name="Ward A",
            shift_date=date.today(),
            status=HandoverStatus.SUBMITTED,
            submitted_at=datetime.now(IST),
            created_by=nurse.id,
        )
    )
    db.commit()

    stats = get_nurse_dashboard_stats_service(db)

    assert stats["success"] is True
    assert stats["queue_today"]["scheduled"] == 1
    assert stats["queue_today"]["total"] == 1
    assert stats["beds"]["occupied_count"] == 1
    assert stats["alerts"]["active_count"] == 1
    assert stats["alerts"]["critical_count"] == 1
    assert stats["handovers"]["submitted_count"] == 1
    assert stats["handovers"]["awaiting_take_over_count"] == 1


def test_take_over_handover_notifies_outgoing_nurse(db, nurse_seed):
    nurse_a = nurse_seed["nurse_a"]
    nurse_b = nurse_seed["nurse_b"]
    patient = nurse_seed["patient"]

    handover = ShiftHandover(
        handover_uid="HO-2026-000010",
        outgoing_nurse_id=nurse_a.id,
        ward_name="Ward A",
        shift_date=date.today(),
        status=HandoverStatus.SUBMITTED,
        submitted_at=datetime.now(IST),
        created_by=nurse_a.id,
    )
    db.add(handover)
    db.flush()
    db.add(
        ShiftHandoverPatient(
            handover_id=handover.id,
            patient_id=patient.id,
            patient_name="Ramesh Patil",
            bed_number="B-12",
            patient_summary="Stable",
            created_by=nurse_a.id,
        )
    )
    db.commit()

    result = take_over_handover_service(
        db,
        handover.id,
        nurse_b.id,
        ShiftHandoverTakeOver(take_over_notes="Taking evening shift"),
    )

    assert result["replacement_nurse_id"] == nurse_b.id
    db.refresh(handover)
    assert handover.replacement_nurse_id == nurse_b.id

    notif = (
        db.query(Notification)
        .filter(
            Notification.user_id == nurse_a.id,
            Notification.notification_type == NotificationType.HANDOVER_TAKEN_OVER,
        )
        .first()
    )
    assert notif is not None
    assert "Anita" in (notif.message or "")


def test_assign_alert_notifies_assigned_nurse(db, nurse_seed):
    nurse_a = nurse_seed["nurse_a"]
    nurse_b = nurse_seed["nurse_b"]
    patient = nurse_seed["patient"]

    alert = EmergencyAlert(
        alert_uid="EA-2026-000099",
        patient_id=patient.id,
        alert_type=AlertType.MANUAL,
        severity=AlertSeverity.HIGH,
        title="Manual high alert",
        status=AlertStatus.ACTIVE,
        is_active=True,
        triggered_by=nurse_a.id,
    )
    db.add(alert)
    db.commit()

    assign_alert_service(
        db,
        alert.id,
        EmergencyAlertAssign(assigned_nurse_id=nurse_b.id),
        nurse_id=nurse_a.id,
    )

    notif = (
        db.query(Notification)
        .filter(
            Notification.user_id == nurse_b.id,
            Notification.notification_type == NotificationType.EMERGENCY_ALERT,
        )
        .first()
    )
    assert notif is not None
    assert notif.title == "Manual high alert"


def test_nurse_notification_unread_and_mark_read(db, nurse_seed):
    nurse = nurse_seed["nurse_a"]

    create_notification(
        db,
        user_id=nurse.id,
        title="Shift updated by admin",
        message="Shift name: Morning",
        notification_type=NotificationType.SHIFT_UPDATED,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=nurse.id,
    )

    assert get_unread_count(db, nurse.id) == 1

    notif = db.query(Notification).filter(Notification.user_id == nurse.id).first()
    marked = mark_as_read(db, nurse.id, notif.id)
    assert marked.is_read is True
    assert get_unread_count(db, nurse.id) == 0
