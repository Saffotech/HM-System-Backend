from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_other_visit_schema import (
    DepartmentListResponse,
    OtherVisitCreate,
    OtherVisitListResponse,
    OtherVisitResponse,
    OtherVisitUpdate,
    OtherVisitVoidRequest,
)
from Services.nurse_other_visit_service import (
    create_other_visit_service,
    list_departments_service,
    list_other_visits_service,
    update_other_visit_service,
    void_other_visit_service,
)

router = APIRouter(
    prefix="/nurse/other-visits",
    tags=["Nurse Other Visits"],
)


@router.post(
    "",
    response_model=OtherVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_other_visit(
    payload: OtherVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_other_visits:create")),
):
    return create_other_visit_service(db, payload, current_user)


@router.get(
    "",
    response_model=OtherVisitListResponse,
)
def list_other_visits(
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
    department_id: int | None = Query(None, ge=1),
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
    _: bool = Depends(PermissionChecker("nurse_other_visits:view")),
):
    return list_other_visits_service(
        db,
        patient_id=patient_id,
        patient_uid=patient_uid,
        department_id=department_id,
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
    "/departments",
    response_model=DepartmentListResponse,
)
def list_departments(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_other_visits:view")),
):
    return list_departments_service(
        db,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/{visit_id}",
    response_model=OtherVisitResponse,
)
def update_other_visit(
    payload: OtherVisitUpdate,
    visit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_other_visits:update")),
):
    return update_other_visit_service(db, visit_id, payload, current_user)


@router.put(
    "/{visit_id}/void",
    response_model=OtherVisitResponse,
)
def void_other_visit(
    payload: OtherVisitVoidRequest,
    visit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_other_visits:update")),
):
    return void_other_visit_service(db, visit_id, payload, current_user)
