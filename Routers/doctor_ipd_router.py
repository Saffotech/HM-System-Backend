from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.doctor_ipd_schema import (
    DoctorIpdAdmissionListResponse,
    PaginationSchema,
)
from Services.doctor_ipd_service import list_doctor_ipd_admissions_service

router = APIRouter(
    prefix="/doctor/ipd-admissions",
    tags=["Doctor IPD"],
)


@router.get(
    "",
    response_model=DoctorIpdAdmissionListResponse,
    status_code=status.HTTP_200_OK,
)
def list_doctor_ipd_admissions(
    pagination: PaginationSchema = Depends(),
    status_filter: Optional[str] = Query(
        default="admitted",
        alias="status",
        description="admitted | discharged | cancelled | all (admit/discharge aliases allowed)",
    ),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return list_doctor_ipd_admissions_service(
        db=db,
        doctor_id=current_user.id,
        status=status_filter,
        from_date=from_date,
        to_date=to_date,
        search=search,
        page=pagination.page,
        page_size=pagination.page_size,
    )
