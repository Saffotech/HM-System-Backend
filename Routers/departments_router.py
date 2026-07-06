from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.department_schema import (
    DepartmentActionResponse,
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentOut,
    DepartmentUpdate,
)
from Services import department_service

router = APIRouter(prefix="/departments", tags=["Admin - Departments"])


@router.get("/", response_model=DepartmentListResponse)
def list_departments(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    departments = department_service.list_departments(db, is_active=is_active)
    return DepartmentListResponse(total=len(departments), departments=departments)


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return department_service.get_department_by_id(db, department_id)


@router.post("/", response_model=DepartmentActionResponse, status_code=201)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    department = department_service.create_department(db, data, current_user)
    return DepartmentActionResponse(
        message="Department created successfully",
        department=department,
    )


@router.patch("/{department_id}", response_model=DepartmentActionResponse)
def update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    department = department_service.update_department(db, department_id, data, current_user)
    return DepartmentActionResponse(
        message="Department updated successfully",
        department=department,
    )
