"""IPD insurance APIs — patients, claims, admission insurance profile."""
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.ipd_schema import IpdInsuranceClaimUpdate, IpdInsurancePaymentIn
from Services import ipd_insurance_service as svc

router = APIRouter(prefix="/ipd/insurance", tags=["IPD Insurance"])


@router.get("/patients")
def list_insurance_patients(
    search: Optional[str] = None,
    claim_type: Optional[str] = Query(
        None, description="cashless | pay_and_claim (default cashless)"
    ),
    status: Optional[str] = None,
    ward: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:list")),
):
    return svc.list_insurance_patients(
        db,
        search=search,
        claim_type=claim_type,
        status=status,
        ward=ward,
        page=page,
        limit=limit,
    )


@router.get("/patients/{patient_key}")
def get_insurance_patient(
    patient_key: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:view")),
):
    claim = svc.get_latest_claim_for_patient_key(db, patient_key)
    return svc.serialize_patient_bundle(db, claim)


@router.put("/patients/{patient_key}")
def update_insurance_patient(
    payload: IpdInsuranceClaimUpdate,
    patient_key: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:create")),
):
    return svc.update_patient_insurance(db, patient_key, payload)


@router.get("/bills")
def list_insurance_bills(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:view")),
):
    return svc.list_insurance_bills(db, search=search, page=page, limit=limit)


@router.get("/claims/{claim_id}")
def get_insurance_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:view")),
):
    claim = svc.get_claim_flexible(db, claim_id)
    return svc.serialize_claim(db, claim)


@router.put("/claims/{claim_id}")
def update_insurance_claim(
    payload: IpdInsuranceClaimUpdate,
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:create")),
):
    claim = svc.get_claim_flexible(db, claim_id)
    svc.update_claim(db, claim, payload)
    return svc.serialize_claim(db, svc.get_claim_by_id(db, claim.id))


@router.post("/claims/{claim_id}/payments/insurance", status_code=201)
def add_insurance_payment(
    payload: IpdInsurancePaymentIn,
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:pay")),
):
    claim = svc.get_claim_flexible(db, claim_id)
    return svc.add_payment(db, claim, payload, kind="insurance")


@router.post("/claims/{claim_id}/payments/patient", status_code=201)
def add_patient_payment(
    payload: IpdInsurancePaymentIn,
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:bill:pay")),
):
    claim = svc.get_claim_flexible(db, claim_id)
    return svc.add_payment(db, claim, payload, kind="patient")


@router.get("/admissions/{admission_id}")
def get_admission_insurance(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:patients:view")),
):
    return svc.get_admission_insurance(db, admission_id)


@router.put("/admissions/{admission_id}")
def update_admission_insurance(
    payload: IpdInsuranceClaimUpdate,
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd:admission:create")),
):
    return svc.update_admission_insurance(db, admission_id, payload)
