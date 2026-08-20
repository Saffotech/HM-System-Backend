from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Schemas.doctor_patient_clinical_schema import (
    DoctorVitalsResponse,
    DoctorNotesResponse,
)
from Services.doctor_patient_clinical_service import (
    get_patient_vitals_service,
    get_patient_notes_service,
)
from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit

router = APIRouter(
    prefix="/doctor/patients",
    tags=["Doctor Patient Clinical"],
)


# ==========================================================
# Get Patient Vitals
# ==========================================================

@router.get(
    "/{patient_id}/vitals",
    response_model=DoctorVitalsResponse,
    status_code=status.HTTP_200_OK
)
def get_patient_vitals(
    patient_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_vitals:view"))
):
    result = get_patient_vitals_service(
        db=db,
        doctor_id=current_user.id,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
    )
    doctor_audit.log_patient_vitals_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        patient_id=patient_id,
        from_date=from_date,
        to_date=to_date,
    )
    return result


# ==========================================================
# Get Patient Nursing Notes
# ==========================================================

@router.get(
    "/{patient_id}/notes",
    response_model=DoctorNotesResponse,
    status_code=status.HTTP_200_OK
)
def get_patient_notes(
    patient_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_notes:view"))
):
    result = get_patient_notes_service(
        db=db,
        doctor_id=current_user.id,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
    )
    doctor_audit.log_patient_notes_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        patient_id=patient_id,
        from_date=from_date,
        to_date=to_date,
    )
    return result
