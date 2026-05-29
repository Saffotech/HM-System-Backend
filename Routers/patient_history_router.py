from datetime import date
from typing import Optional
from fastapi import APIRouter,Depends,status,Query
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user,PermissionChecker
from Models.user import User
from Schemas.patient_history_schema import PaginationSchema
from Services.patient_history_service import (
    get_patients_service,
    get_patient_details_service
)

router = APIRouter(
    prefix="/patients",
    tags=["Patients History"]
)

# ==========================================================
# Get Patients
# ==========================================================

@router.get(
    "",
    status_code=status.HTTP_200_OK
)
def get_patients(

    pagination: PaginationSchema = Depends(),
    filter_date: Optional[date] = Query(default=None),
    month: Optional[int] = Query(default=None,ge=1,le=12),
    year: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):

    result = get_patients_service(

        db=db,
        doctor_id=current_user.id,
        page=pagination.page,
        limit=pagination.limit,
        filter_date=filter_date,
        month=month,
        year=year,
        search=search
    )

    return {
        "success": True,
        "total_patients": result[
            "total_patients"
        ],
        "page": result["page"],
        "limit": result["limit"],
        "patients": result["patients"]
    }


# ==========================================================
# Get Patient Details
# ==========================================================

@router.get(
    "/{patient_uhid}",
    status_code=status.HTTP_200_OK
)
def get_patient_details(

    patient_uhid: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("appointments:view")
    )
):

    patient = get_patient_details_service(

        db=db,

        doctor_id=current_user.id,

        patient_uhid=patient_uhid
    )

    return {

        "success": True,

        "patient_history": patient
    }