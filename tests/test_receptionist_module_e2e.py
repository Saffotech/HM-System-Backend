"""End-to-end service tests for the receptionist module."""
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
from Models.doctor_profile import DoctorProfile
from Models.notification import Notification
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit, Patient
from Models.receptionist_profile import ReceptionistProfile
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffUpdateRequest
from Schemas.receptionist_profile_schema import ReceptionistProfileUpdate
from Services.admin_users_service import update_staff
from Services.notification_service import (
    create_notification,
    get_unread_count,
    mark_as_read,
)
from Services.receptionist_profile_service import (
    get_receptionist_profile,
    update_receptionist_profile,
)
from Services.receptionist_service import (
    get_dashboard,
    get_doctor_queue,
    get_doctors_schedule,
    get_queue_history,
    get_today_queue,
    receptionist_appointment_status_from_query,
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
def receptionist_seed(db):
    dept = Department(name="General Medicine", code="GEN")
    db.add(dept)
    db.flush()

    doctor_role = Role(name="doctor", description="Doctor")
    receptionist_role = Role(name="receptionist", description="Receptionist")
    admin_role = Role(name="admin", description="Admin")
    db.add_all([doctor_role, receptionist_role, admin_role])
    db.flush()

    doctor = User(
        first_name="Adesh",
        last_name="Zinj",
        email="doctor_rec@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept.id,
        is_active=True,
    )
    receptionist = User(
        first_name="Riya",
        last_name="Patel",
        email="receptionist_rec@test.com",
        password="hashed",
        role_id=receptionist_role.id,
        department_id=dept.id,
        is_active=True,
        phone="9000000099",
    )
    admin = User(
        first_name="Hospital",
        last_name="Admin",
        email="admin_rec@test.com",
        password="hashed",
        role_id=admin_role.id,
        is_active=True,
    )
    db.add_all([doctor, receptionist, admin])
    db.flush()

    db.add_all(
        [
            DoctorProfile(
                user_id=doctor.id,
                languages=[],
                shift_name="Morning",
                shift_start_time=datetime.strptime("08:00", "%H:%M").time(),
                shift_end_time=datetime.strptime("16:00", "%H:%M").time(),
            ),
            ReceptionistProfile(user_id=receptionist.id, languages=[]),
        ]
    )
    db.flush()

    patient_paid = Patient(
        patient_uid="P-REC-PAID",
        first_name="Shubham",
        last_name="Chaugule",
        phone="9999999999",
        allergies="None",
        is_active=True,
    )
    patient_unpaid = Patient(
        patient_uid="P-REC-UNPAID",
        first_name="Amit",
        last_name="Kumar",
        phone="8888888888",
        allergies="None",
        is_active=True,
    )
    db.add_all([patient_paid, patient_unpaid])
    db.flush()

    now = datetime.now(IST)
    appointment_paid = Appointment(
        appointment_uid="APT-REC-PAID",
        patient_id=patient_paid.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=now,
        status=AppointmentStatus.scheduled,
    )
    appointment_unpaid = Appointment(
        appointment_uid="APT-REC-UNPAID",
        patient_id=patient_unpaid.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=now,
        status=AppointmentStatus.scheduled,
    )
    appointment_completed = Appointment(
        appointment_uid="APT-REC-DONE",
        patient_id=patient_paid.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=now,
        status=AppointmentStatus.completed,
    )
    db.add_all([appointment_paid, appointment_unpaid, appointment_completed])
    db.flush()

    visit_paid = OpdVisit(
        bill_number="BILL-REC-001",
        token_number="T-REC-001",
        patient_id=patient_paid.id,
        appointment_id=appointment_paid.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        payment_status="paid",
        status="registered",
    )
    db.add(visit_paid)
    db.flush()

    queue = PatientQueue(
        appointment_id=appointment_paid.id,
        patient_id=patient_paid.id,
        patient_name="Shubham Chaugule",
        patient_uhid=patient_paid.patient_uid,
        patient_phone=patient_paid.phone,
        appointment_uid=appointment_paid.appointment_uid,
        doctor_id=doctor.id,
        token_number=1,
        queue_date=date.today(),
        status=QueueStatus.SCHEDULED,
        priority=QueuePriority.NORMAL,
        queue_entered_at=now,
    )
    db.add(queue)
    db.commit()

    return {
        "dept": dept,
        "doctor": doctor,
        "receptionist": receptionist,
        "admin": admin,
        "patient_paid": patient_paid,
        "patient_unpaid": patient_unpaid,
        "appointment_paid": appointment_paid,
        "appointment_unpaid": appointment_unpaid,
        "appointment_completed": appointment_completed,
        "queue": queue,
        "profile": db.query(ReceptionistProfile)
        .filter(ReceptionistProfile.user_id == receptionist.id)
        .first(),
    }


def test_receptionist_dashboard_counts(db, receptionist_seed):
    data = get_dashboard(db)
    assert data["total_patients"] >= 2
    assert data["completed"] >= 1
    assert data["todays_paid_appointments"] >= 1
    assert data["todays_unpaid_appointments"] >= 1


def test_receptionist_today_queue_lists_paid_and_unpaid(db, receptionist_seed):
    result = get_today_queue(db, page=1, limit=20)
    uids = {row["appointment_uid"] for row in result["queue"]}

    assert "APT-REC-PAID" in uids
    assert "APT-REC-UNPAID" in uids

    paid_only = get_today_queue(
        db,
        payment_filter="paid",
        page=1,
        limit=20,
    )
    paid_uids = {row["appointment_uid"] for row in paid_only["queue"]}
    assert "APT-REC-PAID" in paid_uids
    assert "APT-REC-UNPAID" not in paid_uids


def test_receptionist_doctor_queue_filter(db, receptionist_seed):
    doctor = receptionist_seed["doctor"]

    result = get_doctor_queue(
        db,
        doctor_id=doctor.id,
        status="scheduled",
        page=1,
        limit=20,
    )
    assert result["doctor_id"] == doctor.id
    assert any(row["appointment_uid"] == "APT-REC-PAID" for row in result["queue"])


def test_receptionist_queue_history(db, receptionist_seed):
    result = get_queue_history(
        db,
        status="completed",
        page=1,
        limit=20,
    )
    assert any(row["appointment_uid"] == "APT-REC-DONE" for row in result["history"])


def test_receptionist_doctors_schedule(db, receptionist_seed):
    result = get_doctors_schedule(
        db,
        schedule_date=date.today(),
        page=1,
        page_size=10,
    )
    assert result["total"] >= 1
    assert any(row["doctor_id"] == receptionist_seed["doctor"].id for row in result["doctors"])


def test_receptionist_invalid_status_filter():
    with pytest.raises(HTTPException) as exc:
        receptionist_appointment_status_from_query("waiting")
    assert exc.value.status_code == 422


def test_receptionist_profile_get_and_update(db, receptionist_seed):
    receptionist = receptionist_seed["receptionist"]

    profile = get_receptionist_profile(db, receptionist)
    assert profile.user_id == receptionist.id
    assert profile.email == receptionist.email
    assert profile.department is not None

    updated = update_receptionist_profile(
        db,
        receptionist,
        ReceptionistProfileUpdate(
            qualification="Front Desk Diploma",
            experience_years=3,
            bio="Patient guidance specialist",
            phone="9111111111",
            languages=["English", "Hindi"],
        ),
    )
    assert updated.qualification == "Front Desk Diploma"
    assert updated.experience_years == 3
    assert "Hindi" in updated.languages


def test_receptionist_notifications_unread_and_mark_read(db, receptionist_seed):
    receptionist = receptionist_seed["receptionist"]

    create_notification(
        db,
        user_id=receptionist.id,
        title="Shift updated by admin",
        message="Shift name: Evening",
        notification_type=NotificationType.SHIFT_UPDATED,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=receptionist.id,
    )
    create_notification(
        db,
        user_id=receptionist.id,
        title="Department reassigned",
        message="Admin reassigned your department",
        notification_type=NotificationType.ADMIN_UPDATE,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.USER,
        reference_id=receptionist.id,
    )

    assert get_unread_count(db, receptionist.id) == 2
    notif = (
        db.query(Notification)
        .filter(Notification.user_id == receptionist.id)
        .order_by(Notification.id.asc())
        .first()
    )
    mark_as_read(db, receptionist.id, notif.id)
    assert get_unread_count(db, receptionist.id) == 1


def test_admin_shift_change_notifies_receptionist(db, receptionist_seed):
    receptionist = receptionist_seed["receptionist"]
    admin = receptionist_seed["admin"]

    update_staff(
        db,
        receptionist.id,
        StaffUpdateRequest(
            shift_name="Morning",
            shift_start_time="08:00",
            shift_end_time="16:00",
        ),
        admin,
    )

    notif = (
        db.query(Notification)
        .filter(
            Notification.user_id == receptionist.id,
            Notification.notification_type == NotificationType.SHIFT_UPDATED,
        )
        .first()
    )
    assert notif is not None
    assert "Shift" in notif.title
