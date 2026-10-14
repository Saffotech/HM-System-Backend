from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Schemas.tenant_schema import TenantRegisterRequest, TenantRegisterResponse
from Services.tenant_service import register_tenant
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
