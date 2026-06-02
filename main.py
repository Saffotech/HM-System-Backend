from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from Routers import auth
from Routers.roles import router as roles_router
from Models import user, role, department, opd_billing  # noqa: F401
from Routers.opd import router as opd_router
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.doctor_lab_test_order import LabTestOrder
from Models.doctor_patient_queue import PatientQueue  # noqa: F401

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
app.include_router(roles_router)
app.include_router(opd_router)

@app.get("/")
def home():
    return {"message": "Hospital api running.."}

from Routers.doctor_appointment_router import (
    router as appointments_router
)
app.include_router(appointments_router)

from Routers.doctor_patient_queue_router import router as patient_queue_router
app.include_router(patient_queue_router)

from Routers.doctor_patient_history_router import (
    router as patient_router
)

app.include_router(patient_router)


from Routers.doctor_prescription_router import (
    router as prescription_router
)

app.include_router(prescription_router)

from Routers.doctor_lab_test_router import router as lab_test_router
app.include_router(lab_test_router)

