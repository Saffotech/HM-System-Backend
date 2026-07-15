"""HTTP TestClient coverage for receptionist APIs and notifications."""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "receptionist-http-test-secret")
os.environ.setdefault("ALGORITHM", "HS256")

from database import Base, get_db
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
from Routers.receptionist_notification_router import (
    router as receptionist_notification_router,
)
from Routers.receptionist_profile_router import router as receptionist_profile_router
from Routers.receptionist_router import router as receptionist_router
from Services.notification_service import create_notification
from jwt_token import create_access_token


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return compiler.visit_JSON(JSON())


IST = ZoneInfo("Asia/Kolkata")

RECEPTIONIST_PERMS = [
    "patients:view",
    "opd:view",
    "receptionist:view_doctor_schedule",
    "receptionist_profile:view",
    "receptionist_profile:update",
    "receptionist_profile:upload_image",
    "receptionist_profile:delete_image",
    "notifications:view",
    "notifications:update",
]


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed(db_session):
    dept = Department(name="General Medicine", code="GEN")
    db_session.add(dept)
    db_session.flush()

    doctor_role = Role(name="doctor", description="Doctor")
    receptionist_role = Role(name="receptionist", description="Receptionist")
    db_session.add_all([doctor_role, receptionist_role])
    db_session.flush()

    doctor = User(
        first_name="Adesh",
        last_name="Zinj",
        email="http_doctor_rec@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept.id,
        is_active=True,
    )
    receptionist = User(
        first_name="Riya",
        last_name="Patel",
        email="http_receptionist@test.com",
        password="hashed",
        role_id=receptionist_role.id,
        department_id=dept.id,
        is_active=True,
        phone="9000000099",
    )
    db_session.add_all([doctor, receptionist])
    db_session.flush()

    db_session.add_all(
        [
            DoctorProfile(user_id=doctor.id, languages=[]),
            ReceptionistProfile(user_id=receptionist.id, languages=[]),
        ]
    )
    db_session.flush()

    patient = Patient(
        patient_uid="P-HTTP-REC",
        first_name="Shubham",
        last_name="Chaugule",
        phone="9999999999",
        allergies="None",
        is_active=True,
    )
    db_session.add(patient)
    db_session.flush()

    appointment = Appointment(
        appointment_uid="APT-HTTP-REC",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=datetime.now(IST),
        status=AppointmentStatus.scheduled,
    )
    db_session.add(appointment)
    db_session.flush()

    visit = OpdVisit(
        bill_number="BILL-HTTP-REC",
        token_number="T-HTTP-REC",
        patient_id=patient.id,
        appointment_id=appointment.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        payment_status="paid",
        status="registered",
    )
    db_session.add(visit)
    db_session.flush()

    queue = PatientQueue(
        appointment_id=appointment.id,
        patient_id=patient.id,
        patient_name="Shubham Chaugule",
        patient_uhid=patient.patient_uid,
        patient_phone=patient.phone,
        appointment_uid=appointment.appointment_uid,
        doctor_id=doctor.id,
        token_number=1,
        queue_date=date.today(),
        status=QueueStatus.SCHEDULED,
        priority=QueuePriority.NORMAL,
    )
    db_session.add(queue)
    db_session.commit()

    create_notification(
        db_session,
        user_id=receptionist.id,
        title="Shift updated by admin",
        message="Shift name: Morning",
        notification_type=NotificationType.SHIFT_UPDATED,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=receptionist.id,
    )

    return {
        "receptionist": receptionist,
        "doctor": doctor,
        "appointment": appointment,
        "role": receptionist_role,
        "dept": dept,
    }


@pytest.fixture
def client(db_session, seed):
    app = FastAPI()
    app.include_router(receptionist_router)
    app.include_router(receptionist_profile_router)
    app.include_router(receptionist_notification_router)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    token = create_access_token(
        {
            "sub": str(seed["receptionist"].id),
            "role": "receptionist",
            "role_id": seed["role"].id,
            "permissions": RECEPTIONIST_PERMS,
        }
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_receptionist_dashboard_api(client):
    r = client.get("/receptionist/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "total_patients" in body["data"]


def test_receptionist_today_queue_api(client, seed):
    r = client.get("/receptionist/today-queue", params={"page": 1, "limit": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert any(
        item["appointment_uid"] == seed["appointment"].appointment_uid
        for item in body["queue"]
    )


def test_receptionist_doctor_queue_api(client, seed):
    doctor_id = seed["doctor"].id
    r = client.get(
        f"/receptionist/doctor-queue/{doctor_id}",
        params={"page": 1, "limit": 20},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["doctor_id"] == doctor_id


def test_receptionist_queue_history_api(client):
    r = client.get("/receptionist/queue-history", params={"page": 1, "limit": 20})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


def test_receptionist_doctors_schedule_api(client):
    r = client.get(
        "/receptionist/doctors/schedule",
        params={"date": date.today().isoformat(), "page": 1, "page_size": 10},
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


def test_receptionist_profile_api(client):
    r = client.get("/receptionist/profile")
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "http_receptionist@test.com"

    r = client.put(
        "/receptionist/profile",
        json={
            "qualification": "Front Desk Diploma",
            "experience_years": 4,
            "bio": "Patient guidance",
            "languages": ["English"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["qualification"] == "Front Desk Diploma"


def test_receptionist_notification_apis(client):
    r = client.get("/receptionist/notifications/unread-count")
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1

    r = client.get("/receptionist/notifications", params={"page": 1, "limit": 10})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["total"] >= 1
    notif_id = payload["items"][0]["id"]

    r = client.patch(f"/receptionist/notifications/{notif_id}/read")
    assert r.status_code == 200, r.text

    r = client.patch("/receptionist/notifications/read-all")
    assert r.status_code == 200, r.text

    r = client.get("/receptionist/notifications/unread-count")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_auth_required_on_receptionist_routes(db_session, seed):
    app = FastAPI()
    app.include_router(receptionist_profile_router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/receptionist/profile")
        assert r.status_code in (401, 403)
