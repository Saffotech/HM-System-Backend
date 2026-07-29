from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.admin_schema import AdminDashboardResponse
from Schemas.opd_settings_schema import OpdSettingsOut, OpdSettingsUpdate
from Services import admin_service, opd_settings_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return admin_service.get_dashboard(db)


@router.get("/settings/opd", response_model=OpdSettingsOut)
def get_admin_opd_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return opd_settings_service.get_settings(db)


@router.patch("/settings/opd", response_model=OpdSettingsOut)
def update_admin_opd_settings(
    data: OpdSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:list")),
):
    return opd_settings_service.update_settings(db, data, current_user)
