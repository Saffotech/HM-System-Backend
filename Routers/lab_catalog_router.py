from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.lab_test_schema import (
    LabTestActivation,
    LabTestCreate,
    LabTestListResponse,
    LabTestResponse,
    LabTestUpdate,
)
from Services import lab_test_catalog_service as service

router = APIRouter(prefix="/lab-catalog", tags=["Lab Test Catalog"])


@router.get("", response_model=LabTestListResponse)
def list_lab_catalog(
    active: bool | None = Query(None),
    department_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    _: bool = Depends(PermissionChecker("lab_catalog:view")),
):
    tests = service.list_lab_tests(
        db,
        active=active,
        department_id=department_id,
    )
    return LabTestListResponse(total=len(tests), tests=tests)


@router.post("", response_model=LabTestResponse, status_code=status.HTTP_201_CREATED)
def create_lab_catalog_test(
    data: LabTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_catalog:create")),
):
    return service.create_lab_test(db, data, current_user)


@router.patch("/{test_id}", response_model=LabTestResponse)
def update_lab_catalog_test(
    test_id: int,
    data: LabTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_catalog:update")),
):
    return service.update_lab_test(db, test_id, data, current_user)


@router.patch("/{test_id}/activate", response_model=LabTestResponse)
def activate_lab_catalog_test(
    test_id: int,
    data: LabTestActivation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_catalog:activate")),
):
    return service.set_lab_test_active(db, test_id, data, current_user)
