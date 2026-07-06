from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from Models import department, opd_billing, patient, role, user  # noqa: F401
from Models.audit_log import AuditLog  # noqa: F401
from Models.hospital_settings import HospitalSettings  # noqa: F401
from Models.doctor_lab_test_order import LabTestOrder  # noqa: F401
from Models.doctor_patient_queue import PatientQueue  # noqa: F401
from Models.doctor_prescriptions import Prescription, PrescriptionItem  # noqa: F401
from Models.doctor_queue_next_request import DoctorQueueNextRequest  # noqa: F401
from Models.nurse_emergency_alert import EmergencyAlert  # noqa: F401
from Models.nurse_medication_administration import MedicationAdministration  # noqa: F401
from Models.nurse_nursing_notes import NursingNote  # noqa: F401
from Models.nurse_patient_vitals import PatientVitals  # noqa: F401
from Models.nurse_shift_handover import ShiftHandover, ShiftHandoverPatient  # noqa: F401
from Models.pharmacy_dispensing import Dispensing, DispensingItem  # noqa: F401
from Models.lab_result import LabResult,LabResultParameter  # noqa: F401
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

app = FastAPI(title="Hospital Management API")

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
app.include_router(lab_test_router)
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


@app.get("/")
def home():
    return {"message": "Hospital api running.."}
