from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Query
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):
    return get_patients_service(
        db=db,
        doctor_id=current_user.id,
        page=pagination.page,
        page_size=pagination.page_size,
        filter_date=filter_date,
        month=month,
        year=year,
        search=search
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):
    patient = get_patient_details_service(
        db=db,
        doctor_id=current_user.id,
        patient_uid=patient_uid
    )

    return {
        "success": True,
        "patient_history": patient
    }
