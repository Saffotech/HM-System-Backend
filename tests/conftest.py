"""Shared fixtures for appointment list tests (SQLite in-memory)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.functions import Function

from database import Base
from Models.department import Department
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import Patient
from Models.user import User
from Services import opd_helpers as h


@compiles(Function, "sqlite")
def _compile_sqlite_function(element, compiler, **kw):
    """Postgres timezone() is unavailable in SQLite test DBs."""
    if element.name.lower() == "timezone":
        return f"date({compiler.process(element.clauses.clauses[1])})"
    return compiler.visit_function(element)


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
def appointment_seed(db):
    dept = Department(name="Cardiology", code="CARD")
    db.add(dept)
    db.flush()

    doctor = User(
        first_name="Adesh",
        last_name="Zinj",
        email="doctor@test.com",
        password="hashed",
        department_id=dept.id,
    )
    db.add(doctor)
    db.flush()

    patient = Patient(
        patient_uid="P-1001",
        first_name="Shubham",
        last_name="Chaugule",
        phone="9999999999",
    )
    db.add(patient)
    db.flush()

    early = Appointment(
        appointment_uid="APT-001",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=h.now_ist().replace(hour=9, minute=0),
        status=AppointmentStatus.scheduled,
    )
    late = Appointment(
        appointment_uid="APT-002",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=h.now_ist().replace(hour=15, minute=0),
        status=AppointmentStatus.scheduled,
    )
    completed = Appointment(
        appointment_uid="APT-003",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=h.now_ist().replace(hour=11, minute=0),
        status=AppointmentStatus.completed,
    )
    db.add_all([early, late, completed])
    db.commit()

    return {
        "patient": patient,
        "doctor": doctor,
        "department": dept,
        "early": early,
        "late": late,
        "completed": completed,
    }
