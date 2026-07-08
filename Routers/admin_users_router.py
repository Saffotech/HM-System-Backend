from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.admin_schema import (
    StaffActionResponse,
    StaffActivateRequest,
    StaffDetailOut,
    StaffListResponse,
    StaffUpdateRequest,
)
from Services import admin_users_service

router = APIRouter(prefix="/users", tags=["Admin - Staff"])


@router.get("/", response_model=StaffListResponse)
def list_staff(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return admin_users_service.list_staff(
        db,
        search=search,
        role_id=role_id,
        is_active=is_active,
        page=page,
        limit=limit,
    )


@router.get("/{user_id}", response_model=StaffDetailOut)
def get_staff(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return admin_users_service.get_staff_by_id(db, user_id)


@router.patch("/{user_id}/activate", response_model=StaffActionResponse)
def activate_staff(
    user_id: int,
    data: StaffActivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:activate")),
):
    return admin_users_service.activate_staff(
        db, user_id, data.is_active, current_user
    )


@router.patch("/{user_id}", response_model=StaffDetailOut)
def update_staff(
    user_id: int,
    data: StaffUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:create")),
):
    return admin_users_service.update_staff(db, user_id, data, current_user)


@router.delete("/{user_id}", response_model=StaffActionResponse)
def delete_staff(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:delete")),
):
    return admin_users_service.delete_staff(db, user_id, current_user)
