"""Patient OPD booking (Visit tab).

Login is still POST /auth/login. These routes use that token and only
return data for the patient linked to it.

Book first, then read the bill, then pay. The token number comes back
when the bill is created. The profile (GET /patient/me) is in
patient_profile_router.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from Models.user import User
from Schemas.patient_portal_schema import PatientBookAppointment, PatientPayAppointment
from Services import patient_portal_service

router = APIRouter(prefix="/patient", tags=["Patient"])


@router.get("/departments")
def departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.list_departments(db, current_user)


@router.get("/departments/{department_id}/doctors")
def doctors(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.list_doctors(db, current_user, department_id)


@router.get("/doctors/{doctor_id}/slots")
def slots(
    doctor_id: int,
    department_id: int = Query(...),
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.list_slots(
        db, current_user, doctor_id, department_id, date
    )


@router.post("/appointments", status_code=201)
def book_appointment(
    data: PatientBookAppointment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.book(db, current_user, data)


@router.get("/appointments")
def list_my_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.my_appointments(db, current_user)


@router.get("/appointments/{appointment_id}/bill")
def preview_bill(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.bill_preview(db, current_user, appointment_id)


@router.post("/appointments/{appointment_id}/bill", status_code=201)
def create_bill(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.create_bill(db, current_user, appointment_id)


@router.post("/appointments/{appointment_id}/pay")
def pay_bill(
    appointment_id: int,
    data: PatientPayAppointment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_portal_service.pay(db, current_user, appointment_id, data)
