"""End-to-end service tests for the doctor clinical module.

Covers: queue → start → consultation save (+ Rx) → lab → appointments
stats → patient history → notifications → profile → admin shift notify.
"""
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
from Models.doctor_lab_test_order import LabTestOrder, LabTestStatus
from Models.doctor_patient_queue import PatientQueue, QueuePriority, QueueStatus
from Models.doctor_prescriptions import Prescription
from Models.doctor_profile import DoctorProfile
from Models.nurse_medication_administration import MedicationAdministration  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.notification import Notification
from Models.opd_billing import Appointment, AppointmentStatus, Bed  # noqa: F401
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffUpdateRequest
from Schemas.doctor_consultation_schema import (
    ConsultationPrescriptionPayload,
    SaveConsultationRequest,
)
from Schemas.doctor_lab_test_schema import LabTestCreate
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Schemas.doctor_prescription_schema import PrescriptionItemCreate
from Schemas.doctor_profile_schema import DoctorProfileUpdate
from Services.admin_users_service import update_staff
from Services.doctor_appointment_service import (
    get_appointment_by_id_service,
    get_dashboard_stats_service,
    get_today_appointments_service,
)
from Services.doctor_consultation_service import (
    get_consultation_context_service,
    save_consultation_service,
)
from Services.doctor_lab_test_service import (
    cancel_lab_test_service,
    create_lab_test_service,
    get_lab_test_by_id_service,
)
from Services.doctor_patient_history_service import (
    get_patient_details_service,
    get_patients_service,
)
from Services.doctor_patient_queue_service import (
    get_today_queue_service,
    complete_consultation_service,
)
from Services.doctor_profile_service import get_doctor_profile, update_doctor_profile
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
def doctor_seed(db):
    dept = Department(name="Cardiology", code="CARD")
    db.add(dept)
    db.flush()

    doctor_role = Role(name="doctor", description="Clinical doctor")
    admin_role = Role(name="admin", description="Admin")
    db.add_all([doctor_role, admin_role])
    db.flush()

    doctor = User(
        first_name="Adesh",
        last_name="Zinj",
        email="doctor_e2e@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept.id,
        is_active=True,
        phone="9000000001",
    )
    other_doctor = User(
        first_name="Other",
        last_name="Doc",
        email="other_doc@test.com",
        password="hashed",
        role_id=doctor_role.id,
        department_id=dept.id,
        is_active=True,
    )
    admin = User(
        first_name="Hospital",
        last_name="Admin",
        email="admin_e2e@test.com",
        password="hashed",
        role_id=admin_role.id,
        is_active=True,
    )
    db.add_all([doctor, other_doctor, admin])
    db.flush()

    profile = DoctorProfile(
        user_id=doctor.id,
        qualification="MBBS",
        languages=[],
        is_profile_completed=False,
    )
    db.add(profile)
    db.flush()

    patient = Patient(
        patient_uid="P-DOC-1001",
        first_name="Shubham",
        last_name="Chaugule",
        phone="9999999999",
        allergies="None",
        is_active=True,
    )
    db.add(patient)
    db.flush()

    appointment = Appointment(
        appointment_uid="APT-DOC-001",
        patient_id=patient.id,
        doctor_id=doctor.id,
        department_id=dept.id,
        scheduled_at=datetime.now(IST),
        status=AppointmentStatus.scheduled,
    )
    db.add(appointment)
    db.flush()

    visit = OpdVisit(
        bill_number="BILL-DOC-001",
        token_number="T-DOC-001",
        patient_id=patient.id,
        appointment_id=appointment.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        payment_status="paid",
        status="registered",
    )
    db.add(visit)
    db.flush()

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
        status=QueueStatus.WAITING,
        priority=QueuePriority.NORMAL,
    )
    db.add(queue)
    db.commit()

    return {
        "dept": dept,
        "doctor": doctor,
        "other_doctor": other_doctor,
        "admin": admin,
        "profile": profile,
        "patient": patient,
        "appointment": appointment,
        "queue": queue,
        "visit": visit,
        "doctor_role": doctor_role,
        "admin_role": admin_role,
    }


# ---------------------------------------------------------------------------
# Full clinical E2E path
# ---------------------------------------------------------------------------

def test_doctor_clinical_flow_end_to_end(db, doctor_seed):
    doctor = doctor_seed["doctor"]
    appointment = doctor_seed["appointment"]
    queue = doctor_seed["queue"]
    patient = doctor_seed["patient"]

    # 1) Today queue lists paid + queued patients
    today_queue = get_today_queue_service(db, doctor.id)
    assert len(today_queue) == 1
    assert today_queue[0].id == queue.id

    # 2) Consultation context (queue still waiting — no start step)
    ctx = get_consultation_context_service(db, appointment.id, doctor.id)
    assert ctx["success"] is True
    assert ctx["appointment"]["id"] == appointment.id
    assert ctx["queue"]["id"] == queue.id
    db.refresh(queue)
    assert queue.status == QueueStatus.WAITING

    # 3) Atomic save: clinical + prescription → completes appointment + queue directly
    saved = save_consultation_service(
        db,
        SaveConsultationRequest(
            appointment_id=appointment.id,
            clinical=CompleteConsultationSchema(
                symptoms="Chest pain",
                diagnosis="Angina",
                notes="Advise rest",
            ),
            prescription=ConsultationPrescriptionPayload(
                diagnosis="Angina",
                notes="Take after food",
                items=[
                    PrescriptionItemCreate(
                        medicine_name="Aspirin",
                        dosage="75mg",
                        frequency="OD",
                        duration=7,
                        instructions="After food",
                    )
                ],
            ),
        ),
        doctor.id,
    )
    assert saved["success"] is True
    assert saved["appointment"]["status"] == "completed"
    assert saved["queue"]["status"] == "completed"
    assert saved["prescription"] is not None
    assert saved["prescription"]["diagnosis"] == "Angina"

    rx = db.query(Prescription).filter(Prescription.appointment_id == appointment.id).first()
    assert rx is not None
    assert len(rx.items) == 1
    assert rx.items[0].medicine_name == "Aspirin"

    # 5) Lab order on completed (or any) appointment belonging to doctor
    lab = create_lab_test_service(
        db,
        LabTestCreate(
            appointment_id=appointment.id,
            test_name="ECG",
            category="Cardiology",
            priority="Urgent",
            clinical_notes="Rule out ischemia",
        ),
        doctor.id,
    )
    assert lab.test_name == "ECG"
    status_val = lab.status.value if hasattr(lab.status, "value") else str(lab.status)
    assert status_val.lower() in ("ordered", "labteststatus.ordered")

    lab_detail = get_lab_test_by_id_service(db, lab.id, doctor.id)
    detail_id = lab_detail["id"] if isinstance(lab_detail, dict) else lab_detail.id
    assert detail_id == lab.id

    # 6) Appointments stats / today / detail
    stats = get_dashboard_stats_service(db, doctor.id)
    assert stats["today_appointments"] >= 1
    assert stats["completed_consultations"] >= 1

    today_appts = get_today_appointments_service(db, doctor.id)
    assert any(a["id"] == appointment.id for a in today_appts)

    detail = get_appointment_by_id_service(db, appointment.id, doctor.id)
    assert detail["diagnosis"] == "Angina"

    # 7) Patient history list / details (completed appointments only)
    patients = get_patients_service(db, doctor.id, page=1, page_size=20)
    assert patients["success"] is True
    assert patients["total"] >= 1
    assert any(item.get("patient_uid") == patient.patient_uid for item in patients["items"])

    history = get_patient_details_service(db, doctor.id, patient.patient_uid)
    assert isinstance(history, list)
    assert len(history) >= 1

    # 8) Cancel lab order still ordered
    cancelled = cancel_lab_test_service(db, lab.id, doctor.id)
    assert cancelled["message"]
    order = db.query(LabTestOrder).filter(LabTestOrder.id == lab.id).first()
    assert order.status == LabTestStatus.CANCELLED


def test_cannot_complete_consultation_for_another_doctor(db, doctor_seed):
    with pytest.raises(HTTPException) as exc:
        complete_consultation_service(
            db,
            doctor_seed["queue"].id,
            doctor_seed["other_doctor"].id,
        )
    assert exc.value.status_code == 404


def test_cannot_save_consultation_twice(db, doctor_seed):
    doctor = doctor_seed["doctor"]
    appointment = doctor_seed["appointment"]

    save_consultation_service(
        db,
        SaveConsultationRequest(
            appointment_id=appointment.id,
            clinical=CompleteConsultationSchema(diagnosis="Done"),
        ),
        doctor.id,
    )

    with pytest.raises(HTTPException) as exc:
        save_consultation_service(
            db,
            SaveConsultationRequest(
                appointment_id=appointment.id,
                clinical=CompleteConsultationSchema(diagnosis="Again"),
            ),
            doctor.id,
        )
    assert exc.value.status_code == 400


def test_duplicate_lab_test_rejected(db, doctor_seed):
    doctor = doctor_seed["doctor"]
    appointment = doctor_seed["appointment"]

    create_lab_test_service(
        db,
        LabTestCreate(
            appointment_id=appointment.id,
            test_name="CBC",
            category="Pathology",
        ),
        doctor.id,
    )
    with pytest.raises(HTTPException) as exc:
        create_lab_test_service(
            db,
            LabTestCreate(
                appointment_id=appointment.id,
                test_name="CBC",
                category="Pathology",
            ),
            doctor.id,
        )
    assert exc.value.status_code == 400


def test_doctor_notifications_unread_and_mark_read(db, doctor_seed):
    doctor = doctor_seed["doctor"]

    create_notification(
        db,
        user_id=doctor.id,
        title="Paid Appointment Confirmed",
        message="Patient ready",
        notification_type=NotificationType.NEW_APPOINTMENT,
        source_module=SourceModule.OPD_BILLING,
        reference_type=ReferenceType.APPOINTMENT,
        reference_id=doctor_seed["appointment"].id,
    )
    create_notification(
        db,
        user_id=doctor.id,
        title="Shift updated by admin",
        message="Shift name: Morning",
        notification_type=NotificationType.SHIFT_UPDATED,
        source_module=SourceModule.ADMIN,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=doctor.id,
    )

    assert get_unread_count(db, doctor.id) == 2
    notif = (
        db.query(Notification)
        .filter(Notification.user_id == doctor.id)
        .order_by(Notification.id.asc())
        .first()
    )
    mark_as_read(db, doctor.id, notif.id)
    assert get_unread_count(db, doctor.id) == 1


def test_doctor_profile_get_and_update(db, doctor_seed):
    doctor = doctor_seed["doctor"]

    profile = get_doctor_profile(db, doctor)
    assert profile.user_id == doctor.id
    assert profile.email == doctor.email

    updated = update_doctor_profile(
        db,
        doctor,
        DoctorProfileUpdate(
            qualification="MD Cardiology",
            experience_years=8,
            bio="Heart specialist",
            phone="9111111111",
            languages=["English", "Hindi"],
        ),
    )
    assert updated.qualification == "MD Cardiology"
    assert updated.experience_years == 8
    assert updated.phone == "9111111111"
    assert "Hindi" in updated.languages


def test_admin_shift_change_notifies_doctor(db, doctor_seed):
    doctor = doctor_seed["doctor"]
    admin = doctor_seed["admin"]

    update_staff(
        db,
        doctor.id,
        StaffUpdateRequest(
            shift_name="Morning",
            shift_start_time="08:00",
            shift_end_time="16:00",
        ),
        admin,
    )

    db.refresh(doctor_seed["profile"])
    assert doctor_seed["profile"].shift_name == "Morning"

    notif = (
        db.query(Notification)
        .filter(
            Notification.user_id == doctor.id,
            Notification.notification_type == NotificationType.SHIFT_UPDATED,
        )
        .first()
    )
    assert notif is not None
    assert "Shift" in notif.title


def test_lab_order_wrong_doctor_rejected(db, doctor_seed):
    with pytest.raises(HTTPException) as exc:
        create_lab_test_service(
            db,
            LabTestCreate(
                appointment_id=doctor_seed["appointment"].id,
                test_name="XRay",
                category="Radiology",
            ),
            doctor_seed["other_doctor"].id,
        )
    assert exc.value.status_code == 404
