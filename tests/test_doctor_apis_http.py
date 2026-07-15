"""HTTP TestClient coverage for all doctor API routes.

Uses in-memory SQLite + real JWT auth (no live Postgres dependency).
"""
from __future__ import annotations

import io
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

# Ensure JWT works even if .env is missing in CI
os.environ.setdefault("SECRET_KEY", "doctor-http-test-secret")
os.environ.setdefault("ALGORITHM", "HS256")

from database import Base, get_db
from Enums.notification import NotificationType, ReferenceType, SourceModule
from Models.department import Department
from Models.doctor_patient_queue import PatientQueue, QueuePriority, QueueStatus
from Models.doctor_profile import DoctorProfile
from Models.nurse_medication_administration import MedicationAdministration  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.notification import Notification
from Models.opd_billing import Appointment, AppointmentStatus, Bed  # noqa: F401
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Routers.doctor_appointment_router import router as appointments_router
from Routers.doctor_consultation_router import router as consultation_router
from Routers.doctor_lab_test_router import router as lab_test_router
from Routers.doctor_notification_router import router as doctor_notification_router
from Routers.doctor_patient_history_router import router as patient_router
from Routers.doctor_patient_queue_router import router as patient_queue_router
from Routers.doctor_prescription_router import router as prescription_router
from Routers.doctor_profile_router import router as doctor_profile_router
from Services.notification_service import create_notification
from jwt_token import create_access_token


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return compiler.visit_JSON(JSON())


IST = ZoneInfo("Asia/Kolkata")

DOCTOR_PERMS = [
    "patients:view",
    "opd:view",
    "prescriptions:create",
    "prescriptions:view",
    "prescriptions:update",
    "prescriptions:delete",
    "lab:create",
    "lab:view",
    "appointments:view",
    "appointments:create",
    "appointments:update",
    "doctor_profile:view",
    "doctor_profile:update",
    "doctor_profile:upload_image",
    "doctor_profile:delete_image",
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
    dept = Department(name="Cardiology", code="CARD")
    db_session.add(dept)
    db_session.flush()

    role = Role(name="doctor", description="Clinical doctor")
    db_session.add(role)
    db_session.flush()

    doctor = User(
        first_name="Aman",
        last_name="Singh",
        email="http_doctor@test.com",
        password="hashed",
        role_id=role.id,
        department_id=dept.id,
        is_active=True,
        phone="9000000001",
    )
    db_session.add(doctor)
    db_session.flush()

    profile = DoctorProfile(
        user_id=doctor.id,
        qualification="MBBS",
        languages=[],
        is_profile_completed=False,
    )
    db_session.add(profile)
    db_session.flush()

    patient = Patient(
        patient_uid="P-HTTP-1001",
        first_name="Shubham",
        last_name="Chaugule",
        phone="9999999999",
        allergies="None",
        is_active=True,
    )
    db_session.add(patient)
    db_session.flush()

    appointment = Appointment(
        appointment_uid="APT-HTTP-001",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=datetime.now(IST),
        status=AppointmentStatus.scheduled,
    )
    db_session.add(appointment)
    db_session.flush()

    visit = OpdVisit(
        bill_number="BILL-HTTP-001",
        token_number="T-HTTP-001",
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
        user_id=doctor.id,
        title="Paid Appointment Confirmed",
        message="Patient ready in queue",
        notification_type=NotificationType.NEW_APPOINTMENT,
        source_module=SourceModule.OPD_BILLING,
        reference_type=ReferenceType.APPOINTMENT,
        reference_id=appointment.id,
    )

    return {
        "doctor": doctor,
        "profile": profile,
        "patient": patient,
        "appointment": appointment,
        "queue": queue,
        "role": role,
        "dept": dept,
    }


@pytest.fixture
def client(db_session, seed):
    app = FastAPI()
    app.include_router(appointments_router)
    app.include_router(consultation_router)
    app.include_router(patient_queue_router)
    app.include_router(patient_router)
    app.include_router(prescription_router)
    app.include_router(doctor_profile_router)
    app.include_router(doctor_notification_router)
    app.include_router(lab_test_router)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    token = create_access_token(
        {
            "sub": str(seed["doctor"].id),
            "role": "doctor",
            "role_id": seed["role"].id,
            "permissions": DOCTOR_PERMS,
        }
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_doctor_profile_apis(client):
    r = client.get("/doctor/profile")
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "http_doctor@test.com"

    r = client.put(
        "/doctor/profile",
        json={
            "qualification": "MD Cardiology",
            "experience_years": 7,
            "bio": "HTTP test bio",
            "languages": ["English", "Hindi"],
            "phone": "9111111111",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qualification"] == "MD Cardiology"
    assert body["experience_years"] == 7

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0c"
        b"IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    r = client.post(
        "/doctor/profile/image",
        files={"file": ("doc.png", io.BytesIO(png), "image/png")},
    )
    assert r.status_code == 200, r.text
    assert "profile_image_url" in r.json() or "message" in r.json()

    r = client.delete("/doctor/profile/image")
    assert r.status_code == 200, r.text


def test_doctor_notification_apis(client):
    r = client.get("/doctor/notifications/unread-count")
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1

    r = client.get("/doctor/notifications", params={"page": 1, "limit": 10})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["total"] >= 1
    notif_id = payload["items"][0]["id"]

    r = client.patch(f"/doctor/notifications/{notif_id}/read")
    assert r.status_code == 200, r.text

    r = client.patch("/doctor/notifications/read-all")
    assert r.status_code == 200, r.text

    r = client.get("/doctor/notifications/unread-count")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_appointment_apis(client, seed):
    appt_id = seed["appointment"].id
    today = date.today().isoformat()

    r = client.get("/appointments/dashboard-stats")
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True

    r = client.get("/appointments/today")
    assert r.status_code == 200, r.text
    assert any(a["id"] == appt_id for a in r.json().get("appointments", []))

    r = client.get("/appointments/history")
    assert r.status_code == 200, r.text

    r = client.get(f"/appointments/by-date/{today}")
    assert r.status_code == 200, r.text

    r = client.get(f"/appointments/{appt_id}")
    assert r.status_code == 200, r.text

    r = client.put(
        f"/appointments/{appt_id}/status",
        json={"status": "cancelled"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["appointment"]["status"] == "cancelled"

    # cancelled → scheduled is rejected by business rules
    r = client.put(
        f"/appointments/{appt_id}/status",
        json={"status": "scheduled"},
    )
    assert r.status_code == 400, r.text


def test_queue_and_consultation_flow(client, seed):
    appt_id = seed["appointment"].id
    queue_id = seed["queue"].id

    r = client.get("/queue/today")
    assert r.status_code == 200, r.text
    assert r.json()["total_queue"] >= 1

    r = client.get(f"/consultations/appointment/{appt_id}")
    assert r.status_code == 200, r.text
    assert r.json()["appointment"]["id"] == appt_id

    r = client.post(
        "/consultations/save",
        json={
            "appointment_id": appt_id,
            "clinical": {
                "symptoms": "Fever",
                "diagnosis": "Viral fever",
                "notes": "Rest advised",
            },
            "prescription": {
                "diagnosis": "Viral fever",
                "notes": "Hydrate",
                "items": [
                    {
                        "medicine_name": "Paracetamol",
                        "dosage": "500mg",
                        "frequency": "Twice daily",
                        "duration": 3,
                        "instructions": "After food",
                    }
                ],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["appointment"]["status"] == "completed"
    assert body["queue"]["status"] == "completed"
    assert body["prescription"] is not None

    r = client.post(
        "/consultations/save",
        json={
            "appointment_id": appt_id,
            "clinical": {"diagnosis": "Again"},
        },
    )
    assert r.status_code == 400, r.text

    r = client.put(
        f"/queue/complete/{queue_id}",
        json={"notes": "late complete"},
    )
    assert r.status_code in (200, 400, 404), r.text


def test_patients_history_apis(client, seed):
    appt_id = seed["appointment"].id
    r = client.post(
        "/consultations/save",
        json={
            "appointment_id": appt_id,
            "clinical": {"diagnosis": "Done for history"},
        },
    )
    assert r.status_code == 200, r.text

    r = client.get("/patients", params={"page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    assert r.json()["total"] >= 1

    uid = seed["patient"].patient_uid
    r = client.get(f"/patients/{uid}")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["patient_history"], list)
    assert len(r.json()["patient_history"]) >= 1


def test_prescription_apis(client, seed):
    appt_id = seed["appointment"].id
    patient_id = seed["patient"].id
    patient_uid = seed["patient"].patient_uid

    # Standalone Rx requires consultation completion first
    r = client.post(
        "/consultations/save",
        json={
            "appointment_id": appt_id,
            "clinical": {"diagnosis": "Pre-rx consult"},
        },
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/prescriptions",
        json={
            "appointment_id": appt_id,
            "diagnosis": "Standalone Rx",
            "notes": "HTTP Rx",
            "items": [
                {
                    "medicine_name": "Aspirin",
                    "dosage": "75mg",
                    "frequency": "OD",
                    "duration": 7,
                    "instructions": "After food",
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    rx_id = r.json()["id"]

    r = client.get(f"/prescriptions/{rx_id}")
    assert r.status_code == 200, r.text

    r = client.get(
        "/prescriptions/patient/history",
        params={"patient_id": patient_id, "patient_uid": patient_uid},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    r = client.get(f"/prescriptions/patient/{patient_id}")
    assert r.status_code == 200, r.text

    r = client.put(
        f"/prescriptions/{rx_id}",
        json={
            "appointment_id": appt_id,
            "diagnosis": "Updated Rx",
            "notes": "Updated",
            "items": [
                {
                    "medicine_name": "Aspirin",
                    "dosage": "150mg",
                    "frequency": "OD",
                    "duration": 10,
                    "instructions": "After food",
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["diagnosis"] == "Updated Rx"

    r = client.delete(f"/prescriptions/{rx_id}")
    assert r.status_code == 200, r.text


def test_lab_test_apis(client, seed):
    appt_id = seed["appointment"].id

    r = client.post(
        "/lab-tests",
        json={
            "appointment_id": appt_id,
            "test_name": "CBC",
            "category": "Blood Test",
            "priority": "Normal",
            "clinical_notes": "Routine",
        },
    )
    assert r.status_code == 201, r.text
    lab_id = r.json()["id"]

    r = client.get("/lab-tests", params={"page": 1, "page_size": 10})
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1

    r = client.get("/lab-tests/reports", params={"page": 1, "page_size": 10})
    assert r.status_code == 200, r.text

    r = client.get(f"/lab-tests/{lab_id}")
    assert r.status_code == 200, r.text

    r = client.put(
        f"/lab-tests/{lab_id}",
        json={"priority": "Urgent", "clinical_notes": "Updated notes"},
    )
    assert r.status_code == 200, r.text

    # Duplicate active order rejected
    r = client.post(
        "/lab-tests",
        json={
            "appointment_id": appt_id,
            "test_name": "CBC",
            "category": "Blood Test",
        },
    )
    assert r.status_code == 400, r.text

    r = client.get(f"/lab-tests/{lab_id}/report")
    assert r.status_code in (200, 404), r.text

    r = client.get(f"/lab-tests/{lab_id}/report/file")
    assert r.status_code in (200, 404), r.text

    r = client.patch(f"/lab-tests/{lab_id}/cancel")
    assert r.status_code == 200, r.text


def test_auth_required_on_doctor_routes(db_session, seed):
    app = FastAPI()
    app.include_router(doctor_profile_router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        r = c.get("/doctor/profile")
        assert r.status_code in (401, 403)
