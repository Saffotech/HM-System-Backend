"""Admin APIs for nurse shift bed allocations.

CRUD routes used by the manager screens. /bulk is registered before
/{allocation_id} so the path is not captured as an id.
"""
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_shift_bed_allocation_schema import (
    NurseShiftBedAllocationBulkCreate,
    NurseShiftBedAllocationBulkResponse,
    NurseShiftBedAllocationCreate,
    NurseShiftBedAllocationDetailResponse,
    NurseShiftBedAllocationListResponse,
    NurseShiftBedAllocationUpdate,
)
from Services.nurse_shift_bed_allocation_service import (
    bulk_create_allocations_service,
    create_allocation_service,
    deactivate_allocation_service,
    delete_allocation_service,
    get_allocation_service,
    list_allocations_service,
    update_allocation_service,
)

router = APIRouter(
    prefix="/admin-manager/nurse-bed-allocations",
    tags=["Admin-Manager - Nurse Bed Allocation"],
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


@router.get("", response_model=NurseShiftBedAllocationListResponse)
def list_allocations(
    nurse_id: int | None = Query(None, ge=1),
    bed_id: int | None = Query(None, ge=1),
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    department_id: int | None = Query(None, ge=1),
    ward_name: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(
        None,
        description="Nurse, bed, ward, shift, or allocation/nurse/bed/department ID",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return list_allocations_service(
        db,
        nurse_id=nurse_id,
        bed_id=bed_id,
        shift_date=shift_date,
        shift_name=shift_name,
        department_id=department_id,
        ward_name=ward_name,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=NurseShiftBedAllocationDetailResponse,
)
def create_allocation(
    body: NurseShiftBedAllocationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:create")),
):
    return create_allocation_service(
        db,
        body,
        assigned_by=current_user.id,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    response_model=NurseShiftBedAllocationBulkResponse,
)
def bulk_create_allocations(
    body: NurseShiftBedAllocationBulkCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:assign")),
):
    return bulk_create_allocations_service(
        db,
        body,
        assigned_by=current_user.id,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@router.get(
    "/{allocation_id}",
    response_model=NurseShiftBedAllocationDetailResponse,
)
def get_allocation(
    allocation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_allocation_service(db, allocation_id)


@router.put(
    "/{allocation_id}",
    response_model=NurseShiftBedAllocationDetailResponse,
)
def update_allocation(
    body: NurseShiftBedAllocationUpdate,
    request: Request,
    allocation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:update")),
):
    return update_allocation_service(
        db,
        allocation_id,
        body,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@router.put(
    "/{allocation_id}/deactivate",
    response_model=NurseShiftBedAllocationDetailResponse,
)
def deactivate_allocation(
    request: Request,
    allocation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:update")),
):
    return deactivate_allocation_service(
        db,
        allocation_id,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@router.delete(
    "/{allocation_id}",
    response_model=NurseShiftBedAllocationDetailResponse,
)
def delete_allocation(
    request: Request,
    allocation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:delete")),
):
    return delete_allocation_service(
        db,
        allocation_id,
        actor=current_user,
        ip_address=_client_ip(request),
    )
