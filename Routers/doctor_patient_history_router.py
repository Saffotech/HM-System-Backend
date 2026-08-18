from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Schemas.doctor_patient_history_schema import (
    PaginationSchema,
    PatientHistoryListResponse,
    PatientHistoryDetailResponse,
)
from Services.doctor_patient_history_service import (
    get_patients_service,
    get_patient_details_service
)
from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit

router = APIRouter(
    prefix="/patients",
    tags=["Doctor Patients History"]
)

# ==========================================================
# Get Patients
# ==========================================================

@router.get(
    "",
    response_model=PatientHistoryListResponse,
    status_code=status.HTTP_200_OK
)
def get_patients(
    pagination: PaginationSchema = Depends(),
    filter_date: Optional[date] = Query(default=None),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    encounter_type: Optional[str] = Query(
        default="all",
        description="opd | ipd | all",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view"))
):
    return get_patients_service(
        db=db,
        doctor_id=current_user.id,
        page=pagination.page,
        page_size=pagination.page_size,
        filter_date=filter_date,
        month=month,
        year=year,
        search=search,
        encounter_type=encounter_type,
    )


# ==========================================================
# Get Patient Details
# ==========================================================

@router.get(
    "/{patient_uid}",
    response_model=PatientHistoryDetailResponse,
    status_code=status.HTTP_200_OK
)
def get_patient_details(
    patient_uid: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    encounter_type: Optional[str] = Query(
        default="all",
        description="opd | ipd | all",
    ),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view"))
):
    result = get_patient_details_service(
        db=db,
        doctor_id=current_user.id,
        patient_uid=patient_uid,
        page=page,
        page_size=page_size,
        encounter_type=encounter_type,
    )
    doctor_audit.log_patient_history_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        patient_uid=patient_uid,
        encounter_type=encounter_type,
    )
    return result
