"""HTTP TestClient coverage for nurse notification APIs."""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "nurse-http-test-secret")
os.environ.setdefault("ALGORITHM", "HS256")

from database import Base, get_db
from Enums.notification import NotificationType, ReferenceType, SourceModule
from Models.department import Department
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.nurse_profile import NurseProfile
from Models.role import Role
from Models.user import User
from Routers.nurse_notification_router import router as nurse_notification_router
from Routers.nurse_profile_router import router as nurse_profile_router
from Services.notification_service import create_notification
from jwt_token import create_access_token


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return compiler.visit_JSON(JSON())


NURSE_PERMS = [
    "patients:view",
    "opd:view",
    "nurse_profile:view",
    "nurse_profile:update",
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
    dept = Department(name="General", code="GEN")
    db_session.add(dept)
    db_session.flush()

    nurse_role = Role(name="nurse", description="Nurse")
    db_session.add(nurse_role)
    db_session.flush()

    nurse = User(
        first_name="Priya",
        last_name="Sharma",
        email="http_nurse@test.com",
        password="hashed",
        role_id=nurse_role.id,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(nurse)
    db_session.flush()

    db_session.add(NurseProfile(user_id=nurse.id, languages=[]))
    db_session.commit()

    create_notification(
        db_session,
        user_id=nurse.id,
        title="Handover taken over",
        message="Anita Patel took over your handover.",
        notification_type=NotificationType.HANDOVER_TAKEN_OVER,
        source_module=SourceModule.NURSE,
        reference_type=ReferenceType.HANDOVER,
        reference_id=12,
    )
    create_notification(
        db_session,
        user_id=nurse.id,
        title="Shift updated by admin",
        message="Shift name: Evening",
        notification_type=NotificationType.SHIFT_UPDATED,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=nurse.id,
    )

    return {"nurse": nurse, "role": nurse_role}


@pytest.fixture
def client(db_session, seed):
    app = FastAPI()
    app.include_router(nurse_notification_router)
    app.include_router(nurse_profile_router)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    token = create_access_token(
        {
            "sub": str(seed["nurse"].id),
            "role": "nurse",
            "role_id": seed["role"].id,
            "permissions": NURSE_PERMS,
        }
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_nurse_profile_api(client):
    r = client.get("/nurse/profile")
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "http_nurse@test.com"


def test_nurse_notification_apis(client):
    r = client.get("/nurse/notifications/unread-count")
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 2

    r = client.get(
        "/nurse/notifications",
        params={"page": 1, "limit": 10, "notification_type": "HANDOVER_TAKEN_OVER"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["total"] >= 1
    notif_id = payload["items"][0]["id"]

    r = client.patch(f"/nurse/notifications/{notif_id}/read")
    assert r.status_code == 200, r.text
    assert r.json()["is_read"] is True

    r = client.patch("/nurse/notifications/read-all")
    assert r.status_code == 200, r.text

    r = client.get("/nurse/notifications/unread-count")
    assert r.status_code == 200
    assert r.json()["count"] == 0
