from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.pharmacy_schema import (
    DispenseHistoryResponse,
    DispenseRequest,
    DispenseResponse,
    PharmacyPrescriptionDetail,
    PharmacyPrescriptionListResponse,
)
from Services import pharmacy_audit_service as pharmacy_audit
from Services import pharmacy_service
from Services.audit_helpers import client_ip, user_agent

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy"])


@router.get("/history", response_model=DispenseHistoryResponse)
def dispense_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date_from: Optional[date] = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    prescription_id: Optional[int] = Query(
        None, ge=1, description="Filter history to one prescription"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:view")),
):
    return pharmacy_service.get_dispense_history(
        db,
        page=page,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        prescription_id=prescription_id,
    )


@router.get("/prescriptions", response_model=PharmacyPrescriptionListResponse)
def list_pharmacy_prescriptions(
    status: str = Query("pending"),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:view")),
):
    return pharmacy_service.list_prescriptions(db, status=status, search=search)


@router.get("/prescriptions/{prescription_id}", response_model=PharmacyPrescriptionDetail)
def get_pharmacy_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:view")),
):
    return pharmacy_service.get_prescription_detail(db, prescription_id)


@router.post(
    "/dispense/{prescription_id}",
    response_model=DispenseResponse,
    status_code=201,
)
def dispense_prescription(
    prescription_id: int,
    data: DispenseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:dispense")),
):
    result = pharmacy_service.dispense_prescription(
        db, prescription_id, data, current_user.id
    )
    pharmacy_audit.log_dispense(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        prescription_id=prescription_id,
        result=result,
        batch_number=data.batch_number,
        remarks=data.remarks,
    )
    return result
