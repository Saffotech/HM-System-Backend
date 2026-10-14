from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.admin_schema import AdminDashboardResponse
from Schemas.audit_schema import AuditLogListResponse
from Schemas.hospital_settings_schema import HospitalSettingsOut, HospitalSettingsUpdate
from Schemas.opd_settings_schema import OpdSettingsOut, OpdSettingsUpdate
from Services import admin_service, audit_service, hospital_settings_service, opd_settings_service

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


@router.get("/settings", response_model=HospitalSettingsOut)
def get_hospital_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("settings:manage")),
):
    return hospital_settings_service.get_settings(db)


@router.patch("/settings", response_model=HospitalSettingsOut)
def update_hospital_settings(
    data: HospitalSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("settings:manage")),
):
    return hospital_settings_service.update_settings(db, data, current_user)


@router.get("/audit", response_model=AuditLogListResponse)
def list_audit_log(
    search: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("audit:view")),
):
    return audit_service.list_audit_logs(
        db,
        search=search,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
