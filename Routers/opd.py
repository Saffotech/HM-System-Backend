"""OPD & billing API — routes only; logic in Services/."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from Models.department import Department
from Models.user import User
from Schemas.opd_schema import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    AssignBedRequest,
    BedOut,
    BillPreviewRequest,
    BillPreviewResponse,
    BillUpdateRequest,
    CollectPayment,
    GenerateBillRequest,
    OpdVisitCreate,
    PatientCreate,
    PatientRegisterRequest,
    QueueResponse,
    RegisterSuccessResponse,
    VisitSuccessResponse,
)
from Schemas.patient_schema import PatientOut, PatientUpdate
from dependencies import PermissionChecker, get_current_user
from Services import appointment_service, bed_service, opd_service

router = APIRouter(prefix="/opd", tags=["OPD-Billing"])


# ── Dashboard ─────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return opd_service.get_dashboard(db)


# ── Patients ──────────────────────────────────────────────────

@router.get("/patient/search")
def search_patient(
    phone: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view")),
):
    return opd_service.search_patient_by_phone(db, phone)


@router.get("/patients")
def list_patients(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view")),
):
    return opd_service.list_patients(db, search=search, page=page, limit=limit)


@router.get("/patient/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view")),
):
    return PatientOut.model_validate(opd_service.get_patient(db, patient_id))


@router.get("/patient/{patient_id}/profile")
def patient_profile(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view")),
):
    return opd_service.get_patient_profile(db, patient_id)


@router.put("/patient/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:update")),
):
    return opd_service.update_patient(db, patient_id, data)


@router.delete("/patient/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:delete")),
):
    return opd_service.delete_patient(db, patient_id)


# ── Departments & doctors ─────────────────────────────────────

@router.get("/departments")
def get_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    depts = db.query(Department).filter(Department.is_active.is_(True)).all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in depts]


@router.get("/doctors/department/{department_id}")
def doctors_by_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    dept, doctors = opd_service.list_doctors_in_department(db, department_id)
    return {
        "department": dept.name,
        "doctors": [
            {
                "id": d.id,
                "name": opd_service.display_name(d.first_name, d.last_name, prefix="Dr. "),
                "department_id": d.department_id,
                "department_name": dept.name,
            }
            for d in doctors
        ],
    }


# ── Billing preview & registration ────────────────────────────

@router.post("/bill/preview", response_model=BillPreviewResponse)
def preview_bill_fees(
    data: BillPreviewRequest,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:view")),
):
    return opd_service.build_bill_preview(data)


@router.post("/patient/preview-bill", response_model=BillPreviewResponse)
def preview_bill_register_body(
    data: PatientCreate,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:view")),
):
    return opd_service.build_bill_preview(
        BillPreviewRequest(
            registration_fee=data.registration_fee,
            consultation_fee=data.consultation_fee,
            gst_percent=data.gst_percent,
        )
    )


@router.post("/patient/register", status_code=201, response_model=RegisterSuccessResponse)
def register_and_pay(
    data: PatientRegisterRequest,
    payment_mode: str = "cash",
    pay_later: bool = False,
    amount_received: Optional[float] = None,
    transaction_reference: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:create")),
):
    return opd_service.register_new_patient(
        db,
        data,
        current_user.id,
        payment_mode,
        pay_later,
        amount_received,
        transaction_reference,
    )


@router.post("/visit", status_code=201, response_model=VisitSuccessResponse)
def create_visit_for_patient(
    data: OpdVisitCreate,
    payment_mode: str = "cash",
    pay_later: bool = False,
    amount_received: Optional[float] = None,
    transaction_reference: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:create")),
):
    return opd_service.create_visit_for_existing_patient(
        db,
        data,
        current_user.id,
        payment_mode,
        pay_later,
        amount_received,
        transaction_reference,
    )


@router.post("/bill/generate", status_code=201, response_model=VisitSuccessResponse)
def generate_bill(
    data: GenerateBillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:create")),
):
    return opd_service.generate_bill(db, data, current_user.id)


@router.get("/visit/{visit_id}/invoice")
def get_invoice(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:view")),
):
    return opd_service.build_invoice(db, visit_id)


# ── Bills & payments ──────────────────────────────────────────

@router.get("/bills")
def list_bills(
    status: Optional[str] = Query(None, description="paid | partial | pending"),
    search: Optional[str] = None,
    today_only: bool = False,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:view")),
):
    return opd_service.list_bills(
        db,
        status=status,
        search=search,
        today_only=today_only,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )


@router.put("/bills/{visit_id}")
def update_bill(
    visit_id: int,
    data: BillUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:update")),
):
    return opd_service.update_bill(db, visit_id, data)


@router.delete("/bills/{visit_id}")
def delete_bill(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:delete")),
):
    return opd_service.delete_bill(db, visit_id)


@router.post("/visit/{visit_id}/pay")
def collect_payment(
    visit_id: int,
    data: CollectPayment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:update")),
):
    return opd_service.collect_payment(db, visit_id, data, current_user.id)


@router.get("/payments/history")
def payment_history(
    search: Optional[str] = None,
    payment_mode: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("billing:view")),
):
    return opd_service.list_payment_history(db, search, payment_mode, page, limit)


@router.get("/queue/today", response_model=QueueResponse)
def today_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return opd_service.fetch_today_queue(db)


# ── Appointments ──────────────────────────────────────────────

@router.post("/appointments", status_code=201, response_model=AppointmentOut)
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:create")),
):
    return appointment_service.create_appointment(db, data, current_user.id)


@router.get("/appointments")
def list_appointments(
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return appointment_service.list_appointments(
        db, status=status, date_from=date_from, date_to=date_to, page=page, limit=limit
    )


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    data: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    return appointment_service.update_appointment(db, appointment_id, data)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    return appointment_service.cancel_appointment(db, appointment_id)


@router.get("/appointments/doctor/{doctor_id}/slots")
def doctor_slots(
    doctor_id: int,
    department_id: int,
    date: str = Query(..., description="ISO date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return appointment_service.doctor_availability(db, doctor_id, department_id, date)


# ── Beds ──────────────────────────────────────────────────────

@router.get("/beds")
def list_beds(
    ward: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return bed_service.list_beds(db, ward=ward, status=status, search=search)


@router.get("/beds/ward/{ward_name}")
def ward_beds(
    ward_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return bed_service.ward_status(db, ward_name)


@router.post("/beds/assign", response_model=BedOut)
def assign_bed(
    data: AssignBedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:create")),
):
    return bed_service.assign_bed(db, data)


@router.post("/beds/{bed_id}/release", response_model=BedOut)
def release_bed(
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:create")),
):
    return bed_service.release_bed(db, bed_id)
