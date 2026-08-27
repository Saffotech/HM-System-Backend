from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_doctor_visit_schema import (
    NurseDoctorListResponse,
    NurseDoctorVisitCreate,
    NurseDoctorVisitListResponse,
    NurseDoctorVisitResponse,
    NurseDoctorVisitUpdate,
    NurseDoctorVisitVoidRequest,
)
from Services.audit_helpers import client_ip, user_agent
from Services import nurse_audit_service as nurse_audit
from Services.nurse_doctor_visit_service import (
    create_doctor_visit_service,
    list_active_doctors_service,
    list_doctor_visits_service,
    update_doctor_visit_service,
    void_doctor_visit_service,
)

router = APIRouter(
    prefix="/nurse/doctor-visits",
    tags=["Nurse Doctor Visits"],
)


@router.post(
    "",
    response_model=NurseDoctorVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor_visit(
    payload: NurseDoctorVisitCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_doctor_visits:create")),
):
    result = create_doctor_visit_service(db, payload, current_user)
    nurse_audit.log_doctor_visit_create(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        result=result,
    )
    return result


@router.get(
    "",
    response_model=NurseDoctorVisitListResponse,
)
def list_doctor_visits(
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
    doctor_id: int | None = Query(None, ge=1),
    visit_date: date | None = Query(None),
    search: str | None = Query(None),
    allocated_only: bool = Query(
        False,
        description="If true, only visits for patients on beds allocated to the current nurse.",
    ),
    assignment_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_doctor_visits:view")),
):
    return list_doctor_visits_service(
        db,
        patient_id=patient_id,
        patient_uid=patient_uid,
        doctor_id=doctor_id,
        visit_date=visit_date,
        search=search,
        allocated_only=allocated_only,
        allocation_nurse_id=current_user.id if allocated_only else None,
        assignment_date=assignment_date,
        shift_name=shift_name,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/doctors",
    response_model=NurseDoctorListResponse,
)
def list_active_doctors(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_doctor_visits:view")),
):
    return list_active_doctors_service(
        db,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/{visit_id}",
    response_model=NurseDoctorVisitResponse,
)
def update_doctor_visit(
    payload: NurseDoctorVisitUpdate,
    request: Request,
    visit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_doctor_visits:update")),
):
    result = update_doctor_visit_service(db, visit_id, payload, current_user)
    nurse_audit.log_doctor_visit_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        visit_id=visit_id,
        result=result,
    )
    return result


@router.put(
    "/{visit_id}/void",
    response_model=NurseDoctorVisitResponse,
)
def void_doctor_visit(
    payload: NurseDoctorVisitVoidRequest,
    request: Request,
    visit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_doctor_visits:update")),
):
    result = void_doctor_visit_service(db, visit_id, payload, current_user)
    nurse_audit.log_doctor_visit_void(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        visit_id=visit_id,
        void_reason=payload.void_reason,
    )
    return result
