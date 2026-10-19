from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Schemas.tenant_schema import (
    TenantRegisterRequest,
    TenantRegisterResponse,
    TenantSummary,
)
from Services.tenant_service import get_tenant, list_tenants, register_tenant
from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=TenantRegisterResponse, status_code=201)
def register_hospital(
    data: TenantRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return register_tenant(db, data, current_user)


@router.get("", response_model=list[TenantSummary])
def list_hospitals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return list_tenants(db, current_user)


@router.get("/{tenant_id}", response_model=TenantSummary)
def get_hospital(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return get_tenant(db, current_user, tenant_id)
