from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Request,
    status,
    UploadFile,
    File,
)

from sqlalchemy.orm import Session

from database import get_db

from Models.user import User

from dependencies import (
    get_current_user,
    PermissionChecker,
)

from Schemas.lab_schema import (
    LabReportCreate,
    CompleteTestResponse,
    UploadReportFileResponse,
    UploadReportResponse,
    DashboardResponse,
    LabOrderListResponse,
    LabOrderDetailResponse,
    LabReportListResponse,
    LabReportDetailResponse,
    StatusUpdateResponse,
    ReportSource,
)

from Services.audit_helpers import client_ip, user_agent
from Services import lab_audit_service as lab_audit
from Services.lab_service import (
    get_dashboard_stats,
    get_orders,
    get_order_detail,
    mark_sample_collected,
    mark_processing,
    upload_report,
    get_reports,
    get_report_detail,
    mark_completed,
    upload_report_file,
    get_report_file,
)


router = APIRouter(
    prefix="/lab",
    tags=["Lab Technician"],
)


# ==========================================================
# Dashboard
# ==========================================================

@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_dashboard_stats(
        db=db,
        current_user=current_user,
    )


# ==========================================================
# Orders List
# ==========================================================

@router.get("/orders", response_model=LabOrderListResponse)
def list_orders(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_orders(
        db=db,
        current_user=current_user,
        status=status,
        priority=priority,
        category=category,
        search=search,
        doctor_id=doctor_id,
        patient_id=patient_id,
        patient_uid=patient_uid,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Order Detail
# ==========================================================

@router.get("/orders/{order_id}", response_model=LabOrderDetailResponse)
def order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_order_detail(
        db=db,
        order_id=order_id,
        current_user=current_user,
    )


# ==========================================================
# Sample Collected
# ==========================================================

@router.patch(
    "/orders/{order_id}/sample-collected",
    response_model=StatusUpdateResponse,
)
def sample_collected(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:update")
    ),
):
    result = mark_sample_collected(
        db=db,
        order_id=order_id,
        current_user=current_user,
    )
    if result.get("state_changed"):
        lab_audit.log_sample_collected(
            db,
            actor=current_user,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            order_id=result["order_id"],
            patient_uid=result.get("patient_uid"),
            test_name=result.get("test_name"),
            previous_status="ordered",
            new_status=result["status"],
        )
    return result

# ==========================================================
# Processing (deprecated — Option B no-op, kept for older clients)
# ==========================================================

@router.patch(
    "/orders/{order_id}/processing",
    response_model=StatusUpdateResponse,
    deprecated=True,
)
def processing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:update")
    ),
):
    """Deprecated: processing status removed. Returns sample_collected unchanged."""
    return mark_processing(
        db=db,
        order_id=order_id,
        current_user=current_user,
    )


# ==========================================================
# Upload Report
# ==========================================================

@router.post(
    "/orders/{order_id}/report",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadReportResponse,
)
def create_report(
    order_id: int,
    payload: LabReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:upload_report")
    ),
):
    result = upload_report(
        db=db,
        order_id=order_id,
        payload=payload,
        current_user_id=current_user.id,
        current_user=current_user,
    )
    lab_audit.log_report_upload(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=result["order_id"],
        report_id=result["report_id"],
        patient_uid=result.get("patient_uid"),
        test_name=result.get("test_name"),
        parameter_count=len(payload.parameters or []),
        has_file_ref=bool(payload.report_file),
    )
    return result


# ==========================================================
# Reports List
# ==========================================================

@router.get("/reports", response_model=LabReportListResponse)
def reports(
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    patient_name: str | None = None,
    test_name: str | None = None,
    source: ReportSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_reports(
        db=db,
        current_user=current_user,
        search=search,
        patient_id=patient_id,
        patient_uid=patient_uid,
        patient_name=patient_name,
        test_name=test_name,
        source=source,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Report Detail
# ==========================================================

@router.get("/reports/{report_id}", response_model=LabReportDetailResponse)
def report_detail(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    result = get_report_detail(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
    order = result.get("order") or {}
    lab_audit.log_report_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=result["lab_test_order_id"],
        report_id=result["id"],
        patient_uid=order.get("patient_uid"),
        test_name=order.get("test_name"),
    )
    return result

# ==========================================================
# Complete Test
# ==========================================================

@router.patch(
    "/orders/{order_id}/complete",
    response_model=CompleteTestResponse,
)
def complete_test(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:update")
    ),
):
    result = mark_completed(
        db=db,
        order_id=order_id,
        current_user=current_user,
    )
    if result.get("state_changed"):
        lab_audit.log_complete(
            db,
            actor=current_user,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            order_id=result["order_id"],
            patient_uid=result.get("patient_uid"),
            test_name=result.get("test_name"),
            previous_status="sample_collected",
            new_status=result["status"],
        )
    return result

# ==========================================================
# Upload Report File
# ==========================================================

@router.post(
    "/orders/{order_id}/upload-file",
    response_model=UploadReportFileResponse,
)
def upload_lab_report_file(
    order_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:upload_report")
    ),
):
    result = upload_report_file(
        db=db,
        order_id=order_id,
        file=file,
        current_user_id=current_user.id,
        current_user=current_user,
    )
    lab_audit.log_report_file_upload(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=result["order_id"],
        report_id=result["report_id"],
        patient_uid=result.get("patient_uid"),
        test_name=result.get("test_name"),
        file_name=result.get("file_name"),
        file_type=result.get("file_type"),
        file_size=result.get("file_size"),
        replaced_previous_file=bool(result.get("replaced_previous_file")),
    )
    return result

# ==========================================================
# View Report File
# ==========================================================

@router.get(
    "/reports/{report_id}/file",
)
def view_report_file(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    detail = get_report_detail(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
    order = detail.get("order") or {}
    lab_audit.log_report_file_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=detail["lab_test_order_id"],
        report_id=detail["id"],
        patient_uid=order.get("patient_uid"),
        test_name=order.get("test_name"),
    )
    return get_report_file(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
