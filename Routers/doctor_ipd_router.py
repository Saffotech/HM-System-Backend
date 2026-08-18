from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.doctor_ipd_schema import (
    DoctorIpdAdmissionListResponse,
    DoctorIpdConsultationSaveRequest,
    DoctorIpdConsultationSaveResponse,
    PaginationSchema,
)
from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit
from Services.doctor_ipd_service import (
    list_doctor_ipd_admissions_service,
    save_doctor_ipd_consultation_service,
)


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


@router.post(
    "/{admission_id}/consultations",
    response_model=DoctorIpdConsultationSaveResponse,
    status_code=status.HTTP_200_OK,
)
def save_doctor_ipd_consultation(
    admission_id: int,
    payload: DoctorIpdConsultationSaveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    result = save_doctor_ipd_consultation_service(
        db=db,
        admission_id=admission_id,
        doctor_id=current_user.id,
        payload=payload,
    )
    doctor_audit.log_ipd_consultation_save(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        admission_id=admission_id,
        payload=payload,
        result=result,
    )
    return result
