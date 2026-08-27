from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.lab_schema import LabReportDetailResponse, LabReportListResponse
from Services.audit_helpers import client_ip, user_agent
from Services import nurse_audit_service as nurse_audit
from Services.nurse_lab_report_service import (
    get_nurse_lab_report_file_service,
    get_nurse_lab_report_service,
    list_nurse_lab_reports_service,
)

router = APIRouter(
    prefix="/nurse/lab-reports",
    tags=["Nurse Lab Reports"],
)

_VIEW = PermissionChecker("nurse_lab_reports:view")


def _scope_params(
    allocated_only: bool = Query(
        False,
        description=(
            "If true, only reports for patients on beds allocated to the current nurse. "
            "Default false = all currently occupied beds (hospital-wide)."
        ),
    ),
    assignment_date: date | None = Query(None),
    shift_name: str | None = Query(None),
):
    return {
        "allocated_only": allocated_only,
        "assignment_date": assignment_date,
        "shift_name": shift_name,
    }


@router.get("", response_model=LabReportListResponse)
def list_nurse_lab_reports(
    search: str | None = Query(None),
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
    patient_name: str | None = Query(None),
    test_name: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scope: dict = Depends(_scope_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_VIEW),
):
    return list_nurse_lab_reports_service(
        db,
        nurse_id=current_user.id,
        search=search,
        patient_id=patient_id,
        patient_uid=patient_uid,
        patient_name=patient_name,
        test_name=test_name,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
        **scope,
    )


@router.get("/{report_id}/file")
def download_nurse_lab_report_file(
    request: Request,
    report_id: int = Path(..., ge=1),
    scope: dict = Depends(_scope_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_VIEW),
):
    result = get_nurse_lab_report_file_service(
        db,
        report_id,
        nurse_id=current_user.id,
        **scope,
    )
    nurse_audit.log_lab_report_file_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        report_id=report_id,
    )
    return result


@router.get("/{report_id}", response_model=LabReportDetailResponse)
def get_nurse_lab_report(
    request: Request,
    report_id: int = Path(..., ge=1),
    scope: dict = Depends(_scope_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(_VIEW),
):
    result = get_nurse_lab_report_service(
        db,
        report_id,
        nurse_id=current_user.id,
        **scope,
    )
    order = result.get("order") or {}
    nurse_audit.log_lab_report_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        report_id=result.get("id") or report_id,
        order_id=result.get("lab_test_order_id"),
        patient_id=order.get("patient_id"),
        test_name=order.get("test_name"),
    )
    return result
