"""Admin APIs for nurse shift bed allocations (+ Phase 6 reports/history).

Existing CRUD contracts unchanged. New routes are additive and registered
before /{allocation_id} to avoid path conflicts.
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
from Services.nurse_bed_allocation_reports_service import (
    detect_allocation_conflicts_service,
    get_allocation_dashboard_summary_service,
    get_daily_allocation_report_service,
    get_department_allocation_report_service,
    get_shift_allocation_report_service,
    get_unallocated_beds_report_service,
    get_unassigned_nurses_report_service,
    get_workload_analytics_service,
    list_allocation_history_service,
)
from Services.nurse_shift_bed_allocation_service import (
    bulk_create_allocations_service,
    create_allocation_service,
    deactivate_allocation_service,
    delete_allocation_service,
    get_allocation_service,
    list_allocations_by_bed_service,
    list_allocations_by_nurse_service,
    list_allocations_by_shift_service,
    list_allocations_service,
    update_allocation_service,
)

router = APIRouter(
    prefix="/admin/nurse-bed-allocations",
    tags=["Admin - Nurse Bed Allocation"],
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


# —— Phase 6 additive endpoints (must stay above /{allocation_id}) ——

@router.get("/history")
def list_history(
    allocation_id: int | None = Query(None, ge=1),
    actor_id: int | None = Query(None, ge=1),
    action: str | None = Query(None),
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    nurse_id: int | None = Query(None, ge=1),
    bed_id: int | None = Query(None, ge=1),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return list_allocation_history_service(
        db,
        allocation_id=allocation_id,
        actor_id=actor_id,
        action=action,
        shift_date=shift_date,
        shift_name=shift_name,
        nurse_id=nurse_id,
        bed_id=bed_id,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/dashboard-summary")
def dashboard_summary(
    shift_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_allocation_dashboard_summary_service(db, shift_date=shift_date)


@router.get("/conflicts")
def list_conflicts(
    shift_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return detect_allocation_conflicts_service(db, shift_date=shift_date)


@router.get("/analytics/workload")
def workload_analytics(
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_workload_analytics_service(
        db, shift_date=shift_date, shift_name=shift_name
    )


@router.get("/reports/daily")
def report_daily(
    shift_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_daily_allocation_report_service(db, shift_date=shift_date)


@router.get("/reports/shift")
def report_shift(
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_shift_allocation_report_service(
        db, shift_date=shift_date, shift_name=shift_name
    )


@router.get("/reports/department")
def report_department(
    shift_date: date | None = Query(None),
    department_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_department_allocation_report_service(
        db, shift_date=shift_date, department_id=department_id
    )


@router.get("/reports/nurse-workload")
def report_nurse_workload(
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_workload_analytics_service(
        db, shift_date=shift_date, shift_name=shift_name
    )


@router.get("/reports/unallocated-beds")
def report_unallocated_beds(
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_unallocated_beds_report_service(
        db, shift_date=shift_date, shift_name=shift_name
    )


@router.get("/reports/unassigned-nurses")
def report_unassigned_nurses(
    shift_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return get_unassigned_nurses_report_service(
        db, shift_date=shift_date, shift_name=shift_name
    )


@router.get("/reports/occupied-coverage")
def report_occupied_coverage(
    shift_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    summary = get_allocation_dashboard_summary_service(db, shift_date=shift_date)
    return {
        "success": True,
        "report_type": "occupied_coverage",
        "shift_date": summary["shift_date"],
        "occupied_assigned_beds": summary["occupied_assigned_beds"],
        "occupied_unassigned_beds": summary["occupied_unassigned_beds"],
        "allocated_beds": summary["allocated_beds"],
        "unallocated_beds": summary["unallocated_beds"],
        "coverage_percentage": summary["coverage_percentage"],
    }


@router.get(
    "/by-nurse/{nurse_id}",
    response_model=NurseShiftBedAllocationListResponse,
)
def list_by_nurse(
    nurse_id: int = Path(..., ge=1),
    shift_date: date | None = Query(None),
    is_active: bool | None = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return list_allocations_by_nurse_service(
        db,
        nurse_id,
        shift_date=shift_date,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/by-bed/{bed_id}",
    response_model=NurseShiftBedAllocationListResponse,
)
def list_by_bed(
    bed_id: int = Path(..., ge=1),
    shift_date: date | None = Query(None),
    is_active: bool | None = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return list_allocations_by_bed_service(
        db,
        bed_id,
        shift_date=shift_date,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/by-shift",
    response_model=NurseShiftBedAllocationListResponse,
)
def list_by_shift(
    shift_date: date = Query(...),
    shift_name: str | None = Query(None),
    is_active: bool | None = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("bed_allocation:view")),
):
    return list_allocations_by_shift_service(
        db,
        shift_date=shift_date,
        shift_name=shift_name,
        is_active=is_active,
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
