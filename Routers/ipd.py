"""IPD API routes — admissions, beds, billing, discharge, dashboard."""
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.department import Department
from Models.user import User
from Schemas.ipd_schema import (
    IpdAdmitRequest,
    IpdAdmissionUpdate,
    IpdCollectPaymentRequest,
    IpdDischargeRequest,
    IpdDoctorVisitCreate,
    IpdGenerateBillRequest,
    IpdPatientRegisterRequest,
    IpdPatientRegisterResponse,
    IpdTransferBedRequest,
)
from Services import ipd_billing_service
from Services import ipd_service
from Services import opd_service
from Services import opd_settings_service
from Services import patient_service

router = APIRouter(prefix="/ipd", tags=["IPD"])


# ── Shared hospital reference data (departments & doctors) ─────
# Mirrors the OPD endpoints but gated by IPD permissions so the module
# stays isolated from `opd:view`.

@router.get("/pricing")
def get_pricing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:pricing")),
):
    """
    Read-only hospital pricing for IPD (bed tariff, consult fees, bill items).

    Reuses the same pricing store as Admin/OPD settings without requiring `opd:view`.
    """
    pricing = opd_settings_service.get_pricing(db)
    return {"pricing": pricing.model_dump()}


@router.get("/reference/departments")
def reference_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:list")),
):
    depts = db.query(Department).filter(Department.is_active.is_(True)).all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in depts]


@router.get("/reference/doctors/{department_id}")
def reference_doctors(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:list")),
):
    return opd_service.list_department_doctors_with_fees(db, department_id)


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:dashboard")),
):
    return ipd_service.get_dashboard(db)


@router.get("/admissions")
def list_admissions(
    status: Optional[str] = None,
    ward: Optional[str] = None,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    admission_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:list")),
):
    return ipd_service.list_admissions(
        db,
        status=status,
        ward=ward,
        doctor_id=doctor_id,
        search=search,
        admission_date=admission_date,
        page=page,
        limit=limit,
    )


@router.get("/admissions/{admission_id}")
def admission_detail(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:view")),
):
    return ipd_service.get_admission_detail(db, admission_id)


@router.post("/admissions", status_code=201)
def admit(
    data: IpdAdmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:create")),
):
    return ipd_service.admit_patient(db, data, admitted_by=current_user.id)


@router.put("/admissions/{admission_id}")
def update_admission(
    admission_id: int,
    data: IpdAdmissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:create")),
):
    return ipd_service.update_admission(
        db, admission_id, data, updated_by=current_user.id
    )


@router.post("/admissions/{admission_id}/visits", status_code=201)
def add_visit(
    admission_id: int,
    data: IpdDoctorVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:visits:create")),
):
    return ipd_service.add_doctor_visit(db, admission_id, data, recorded_by=current_user.id)


@router.post("/admissions/{admission_id}/discharge")
def discharge(
    admission_id: int,
    data: IpdDischargeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:discharge")),
):
    return ipd_service.discharge_patient(db, admission_id, data, discharged_by=current_user.id)


@router.post(
    "/patients/register",
    status_code=201,
    response_model=IpdPatientRegisterResponse,
)
def register_patient(
    data: IpdPatientRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:create")),
):
    """
    Create Patient Master (UHID + demographics) only.
    No OPD visit, appointment, token, consultation, or bill.
    """
    patient = patient_service.register_patient_only(db, data, registered_by=current_user.id)
    return IpdPatientRegisterResponse(
        patient_id=patient.id,
        patient_uid=patient.patient_uid,
        patient=patient,
    )


@router.get("/patients")
def list_patients(
    status: Optional[str] = None,
    ward: Optional[str] = None,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    admission_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:list")),
):
    """Alias of admissions list for IPD patient directory."""
    return ipd_service.list_admissions(
        db,
        status=status,
        ward=ward,
        doctor_id=doctor_id,
        search=search,
        admission_date=admission_date,
        page=page,
        limit=limit,
    )


@router.get("/beds")
def list_beds(
    ward: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:beds:view")),
):
    return ipd_service.list_beds(db, ward=ward, status=status, search=search)


@router.get("/beds/wards")
def bed_wards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:beds:view")),
):
    return ipd_service.ward_stats(db)


@router.post("/beds/transfer")
def transfer_bed(
    data: IpdTransferBedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:beds:transfer")),
):
    return ipd_service.transfer_bed(db, data, transferred_by=current_user.id)


@router.get("/billing/running")
def running_bills(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return ipd_service.list_running_bills(db, page=page, limit=limit)


@router.get("/admissions/{admission_id}/billing")
def admission_billing_bundle(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    """Unified billing bundle: auto bed/visit/pharmacy + saved daily/final charges."""
    return ipd_billing_service.get_billing_bundle(db, admission_id)


@router.get("/admissions/{admission_id}/billing/daily")
def admission_daily_billing(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return ipd_billing_service.get_daily_billing(db, admission_id)


@router.put("/admissions/{admission_id}/billing/daily")
def update_admission_daily_billing(
    admission_id: int,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:generate")),
):
    return ipd_billing_service.update_daily_billing(
        db, admission_id, payload, updated_by=current_user.id
    )


@router.get("/admissions/{admission_id}/billing/final")
def admission_final_billing(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return ipd_billing_service.get_final_billing(db, admission_id)


@router.put("/admissions/{admission_id}/billing/final")
def update_admission_final_billing(
    admission_id: int,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:generate")),
):
    return ipd_billing_service.update_final_billing(
        db, admission_id, payload, updated_by=current_user.id
    )


@router.get("/billing/preview/{admission_id}")
def bill_preview(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return ipd_service.build_bill_preview(db, admission_id)


@router.post("/billing/generate", status_code=201)
def generate_bill(
    data: IpdGenerateBillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:generate")),
):
    return ipd_service.generate_bill(db, data, generated_by=current_user.id)


@router.get("/billing/{bill_id}/invoice")
def get_bill_invoice(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return ipd_service.build_invoice(db, bill_id)


@router.post("/billing/{bill_id}/pay")
def pay_bill(
    bill_id: int,
    data: IpdCollectPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:pay")),
):
    return ipd_service.collect_payment(db, bill_id, data, recorded_by=current_user.id)


@router.get("/payments/history")
def payments_history(
    search: Optional[str] = None,
    payment_mode: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:history")),
):
    return ipd_service.payment_history(
        db, search=search, payment_mode=payment_mode, page=page, limit=limit
    )
