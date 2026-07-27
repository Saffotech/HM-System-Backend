"""Admin APIs — Nurse Workforce Management. Additive only."""
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_workforce_schema import (
    NurseWorkforceRosterBulkCreate,
    NurseWorkforceRosterCreate,
    NurseWorkforceShiftCreate,
    NurseWorkforceShiftUpdate,
)
from Services import nurse_workforce_service as svc

router = APIRouter(
    prefix="/admin/nurse-workforce",
    tags=["Admin - Nurse Workforce"],
)


@router.get("/dashboard")
def workforce_dashboard(
    target_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("workforce:view")),
):
    return svc.get_workforce_dashboard_service(db, target_date=target_date)


@router.get("/shifts")
def list_shifts(
    is_active: bool | None = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("workforce:view")),
):
    return svc.list_shifts_service(db, is_active=is_active)


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(
    body: NurseWorkforceShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("workforce:create")),
):
    return svc.create_shift_service(db, body)


@router.put("/shifts/{shift_id}")
def update_shift(
    body: NurseWorkforceShiftUpdate,
    shift_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("workforce:update")),
):
    return svc.update_shift_service(db, shift_id, body)


@router.delete("/shifts/{shift_id}")
def delete_shift(
    shift_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("workforce:delete")),
):
    return svc.delete_shift_service(db, shift_id)


@router.get("/roster")
def list_roster(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    nurse_id: int | None = Query(None, ge=1),
    shift_id: int | None = Query(None, ge=1),
    department_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roster:manage")),
):
    return svc.list_roster_service(
        db,
        date_from=date_from,
        date_to=date_to,
        nurse_id=nurse_id,
        shift_id=shift_id,
        department_id=department_id,
        page=page,
        page_size=page_size,
    )


@router.post("/roster", status_code=status.HTTP_201_CREATED)
def create_roster(
    body: NurseWorkforceRosterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roster:manage")),
):
    return svc.create_roster_service(
        db, body, assigned_by=current_user.id, actor=current_user
    )


@router.post("/roster/bulk", status_code=status.HTTP_201_CREATED)
def bulk_roster(
    body: NurseWorkforceRosterBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roster:manage")),
):
    return svc.bulk_create_roster_service(
        db, body, assigned_by=current_user.id, actor=current_user
    )


@router.delete("/roster/{roster_id}")
def delete_roster(
    roster_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roster:manage")),
):
    return svc.delete_roster_service(db, roster_id, actor=current_user)
