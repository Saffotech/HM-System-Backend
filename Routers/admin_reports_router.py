from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.admin_reports_schema import (
    AdminReportsOverviewResponse,
    AdminVisitsReportResponse,
)
from Services import admin_reports_service

router = APIRouter(prefix="/admin/reports", tags=["Admin - Reports"])


@router.get("/overview", response_model=AdminReportsOverviewResponse)
def reports_overview(
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("reports:view")),
):
    return admin_reports_service.get_reports_overview(
        db, from_date=from_date, to_date=to_date
    )


@router.get("/visits", response_model=AdminVisitsReportResponse)
def reports_visits(
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    department_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("reports:view")),
):
    return admin_reports_service.get_visits_report(
        db,
        from_date=from_date,
        to_date=to_date,
        department_id=department_id,
        page=page,
        limit=limit,
    )
