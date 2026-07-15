"""Admin HR notifications for doctor, nurse, and receptionist."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return compiler.visit_JSON(JSON())


from Enums.notification import NotificationType, ReferenceType
from Models.department import Department
from Models.doctor_profile import DoctorProfile
from Models.nurse_profile import NurseProfile
from Models.notification import Notification
from Models.receptionist_profile import ReceptionistProfile
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffUpdateRequest
from Services.admin_users_service import activate_staff, delete_staff, update_staff


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
def staff_seed(db):
    dept_a = Department(name="Cardiology", code="CARD")
    dept_b = Department(name="Front Desk", code="FD")
    db.add_all([dept_a, dept_b])
    db.flush()

    doctor_role = Role(name="doctor", description="Doctor")
    nurse_role = Role(name="nurse", description="Nurse")
    receptionist_role = Role(name="receptionist", description="Receptionist")
    admin_role = Role(name="admin", description="Admin")
    db.add_all([doctor_role, nurse_role, receptionist_role, admin_role])
    db.flush()

    admin = User(
        first_name="Hospital",
        last_name="Admin",
        email="admin_staff@test.com",
        password="hashed",
        role_id=admin_role.id,
        is_active=True,
    )
    doctor = User(
        first_name="Adesh",
        last_name="Zinj",
        email="doctor_staff@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept_a.id,
        is_active=True,
    )
    nurse = User(
        first_name="Priya",
        last_name="Sharma",
        email="nurse_staff@test.com",
        password="hashed",
        role_id=nurse_role.id,
        department_id=dept_a.id,
        is_active=True,
    )
    receptionist = User(
        first_name="Riya",
        last_name="Patel",
        email="receptionist_staff@test.com",
        password="hashed",
        role_id=receptionist_role.id,
        department_id=dept_b.id,
        is_active=True,
    )
    db.add_all([admin, doctor, nurse, receptionist])
    db.flush()

    db.add_all(
        [
            DoctorProfile(user_id=doctor.id, languages=[]),
            NurseProfile(user_id=nurse.id, languages=[]),
            ReceptionistProfile(user_id=receptionist.id, languages=[]),
        ]
    )
    db.commit()

    return {
        "admin": admin,
        "doctor": doctor,
        "nurse": nurse,
        "receptionist": receptionist,
        "dept_a": dept_a,
        "dept_b": dept_b,
    }


def _notification_for(db, user_id: int, notification_type: NotificationType):
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.notification_type == notification_type,
        )
        .first()
    )


@pytest.mark.parametrize(
    "staff_key",
    ["doctor", "nurse", "receptionist"],
)
def test_admin_shift_change_notifies_staff(db, staff_seed, staff_key):
    staff = staff_seed[staff_key]
    admin = staff_seed["admin"]

    update_staff(
        db,
        staff.id,
        StaffUpdateRequest(
            shift_name="Evening",
            shift_start_time="14:00",
            shift_end_time="22:00",
        ),
        admin,
    )

    notif = _notification_for(db, staff.id, NotificationType.SHIFT_UPDATED)
    assert notif is not None
    assert "Shift" in notif.title
    assert notif.reference_type == ReferenceType.SCHEDULE


@pytest.mark.parametrize(
    "staff_key",
    ["doctor", "nurse", "receptionist"],
)
def test_admin_department_change_notifies_staff(db, staff_seed, staff_key):
    staff = staff_seed[staff_key]
    admin = staff_seed["admin"]
    new_dept_id = staff_seed["dept_b"].id

    update_staff(
        db,
        staff.id,
        StaffUpdateRequest(department_id=new_dept_id),
        admin,
    )

    notif = _notification_for(db, staff.id, NotificationType.ADMIN_UPDATE)
    assert notif is not None
    assert "Department" in notif.title
    assert notif.reference_type == ReferenceType.USER


@pytest.mark.parametrize(
    "staff_key",
    ["doctor", "nurse", "receptionist"],
)
def test_admin_deactivate_notifies_staff(db, staff_seed, staff_key):
    staff = staff_seed[staff_key]
    admin = staff_seed["admin"]

    activate_staff(db, staff.id, is_active=False, actor=admin)

    notif = _notification_for(db, staff.id, NotificationType.ADMIN_UPDATE)
    assert notif is not None
    assert "disabled" in notif.title.lower()


@pytest.mark.parametrize(
    "staff_key",
    ["doctor", "nurse", "receptionist"],
)
def test_admin_delete_notifies_staff(db, staff_seed, staff_key):
    staff = staff_seed[staff_key]
    admin = staff_seed["admin"]

    delete_staff(db, staff.id, actor=admin)

    notif = _notification_for(db, staff.id, NotificationType.ADMIN_UPDATE)
    assert notif is not None
    assert "removed" in notif.title.lower()


def test_admin_self_update_does_not_notify(db, staff_seed):
    admin = staff_seed["admin"]

    update_staff(
        db,
        admin.id,
        StaffUpdateRequest(department_id=staff_seed["dept_a"].id),
        admin,
    )

    count = (
        db.query(Notification)
        .filter(Notification.user_id == admin.id)
        .count()
    )
    assert count == 0
