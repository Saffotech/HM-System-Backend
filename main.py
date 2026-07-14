from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Base, engine, SessionLocal
from Models import department, opd_billing, patient, role, user  # noqa: F401
from Models.audit_log import AuditLog  # noqa: F401
from Models.hospital_settings import HospitalSettings  # noqa: F401
from Models.doctor_lab_test_order import LabTestOrder  # noqa: F401
from Models.doctor_patient_queue import PatientQueue  # noqa: F401
from Models.doctor_prescriptions import Prescription, PrescriptionItem  # noqa: F401
from Models.doctor_profile import DoctorProfile  # noqa: F401
from Models.doctor_queue_next_request import DoctorQueueNextRequest  # noqa: F401
from Models.nurse_profile import NurseProfile  # noqa: F401
from Models.nurse_emergency_alert import EmergencyAlert  # noqa: F401
from Models.nurse_medication_administration import MedicationAdministration  # noqa: F401
from Models.nurse_nursing_notes import NursingNote  # noqa: F401
from Models.nurse_patient_vitals import PatientVitals  # noqa: F401
from Models.nurse_shift_handover import ShiftHandover, ShiftHandoverPatient  # noqa: F401
from Models.pharmacy_dispensing import Dispensing, DispensingItem  # noqa: F401
from Models.lab_result import LabResult,LabResultParameter  # noqa: F401
from Models.notification import Notification  # noqa: F401
from Routers import auth
from Routers.admin_reports_router import router as admin_reports_router
from Routers.admin_router import router as admin_router
from Routers.admin_users_router import router as admin_users_router
from Routers.departments_router import router as departments_router
from Routers.doctor_appointment_router import router as appointments_router
from Routers.doctor_consultation_router import router as consultation_router
from Routers.doctor_lab_test_router import router as lab_test_router
from Routers.doctor_patient_history_router import router as patient_router
from Routers.doctor_patient_queue_router import router as patient_queue_router
from Routers.doctor_prescription_router import router as prescription_router
from Routers.doctor_profile_router import router as doctor_profile_router
from Routers.doctor_notification_router import router as doctor_notification_router
from Routers.nurse_notification_router import router as nurse_notification_router
from Routers.nurse_profile_router import router as nurse_profile_router
from Routers.nurse_emergency_alert_router import router as nurse_emergency_alert_router
from Routers.nurse_medication_administration_router import (
    router as medication_administration_router,
)
from Routers.nurse_nursing_notes_router import router as nurse_notes_router
from Routers.nurse_patient_vitals_router import router as nurse_vitals_router
from Routers.nurse_shift_handover_router import router as nurse_shift_handover_router
from Routers.nurse_dashboard_router import router as nurse_dashboard_router
from Routers.opd import router as opd_router
from Routers.pharmacy import router as pharmacy_router
from Routers.roles import router as roles_router
from Routers.lab_router import router as lab_router
from Routers.super_admin_router import router as super_admin_router
from Routers.receptionist_router import router as receptionist_router

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = SessionLocal()
    try:
        from Services.doctor_appointment_service import mark_past_scheduled_as_no_show

        mark_past_scheduled_as_no_show(db)
    except Exception:
        # Startup must not fail if migration/status rename is mid-rollout.
        db.rollback()
    finally:
        db.close()
    yield


app = FastAPI(title="Hospital Management API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_router)
app.include_router(admin_reports_router)
app.include_router(admin_users_router)
app.include_router(departments_router)
app.include_router(roles_router)
app.include_router(opd_router)
app.include_router(appointments_router)
app.include_router(consultation_router)
app.include_router(patient_queue_router)
app.include_router(patient_router)
app.include_router(prescription_router)
app.include_router(doctor_profile_router)
app.include_router(doctor_notification_router)
app.include_router(lab_test_router)
app.include_router(nurse_notification_router)
app.include_router(nurse_profile_router)
app.include_router(nurse_dashboard_router)
app.include_router(nurse_vitals_router)
app.include_router(nurse_notes_router)
app.include_router(medication_administration_router)
app.include_router(nurse_shift_handover_router)
app.include_router(nurse_emergency_alert_router)
app.include_router(pharmacy_router)
app.include_router(lab_router)
app.include_router(super_admin_router)
app.include_router(receptionist_router)

# Serve uploaded files (doctor photos, lab reports, etc.)
# DB stores paths like "uploads/doctor_image/uuid.jpg"
# API exposes them as "/uploads/doctor_image/uuid.jpg"
_uploads_dir = Path("uploads")
_uploads_dir.mkdir(parents=True, exist_ok=True)
(_uploads_dir / "doctor_image").mkdir(parents=True, exist_ok=True)
(_uploads_dir / "nurse_image").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/")
def home():
    return {"message": "Hospital api running.."}
