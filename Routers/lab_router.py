from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    status,
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
)

from Services.lab_service import (
    get_dashboard_stats,
    get_orders,
    get_order_detail,
    mark_sample_collected,
    mark_processing,
    upload_report,
    get_reports,
    get_report_detail,
)


router = APIRouter(
    prefix="/lab",
    tags=["Lab Technician"],
)


# ==========================================================
# Dashboard
# ==========================================================

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_dashboard_stats(
        db=db,
    )


# ==========================================================
# Orders List
# ==========================================================

@router.get("/orders")
def list_orders(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
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
        status=status,
        priority=priority,
        category=category,
        search=search,
        doctor_id=doctor_id,
        patient_id=patient_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Order Detail
# ==========================================================

@router.get("/orders/{order_id}")
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
    )


# ==========================================================
# Sample Collected
# ==========================================================

@router.patch("/orders/{order_id}/sample-collected")
def sample_collected(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:update")
    ),
):
    return mark_sample_collected(
        db=db,
        order_id=order_id,
    )


# ==========================================================
# Processing
# ==========================================================

@router.patch("/orders/{order_id}/processing")
def processing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:update")
    ),
):
    return mark_processing(
        db=db,
        order_id=order_id,
    )


# ==========================================================
# Upload Report
# ==========================================================

@router.post(
    "/orders/{order_id}/report",
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    order_id: int,
    payload: LabReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:upload_report")
    ),
):
    return upload_report(
        db=db,
        order_id=order_id,
        payload=payload,
        current_user_id=current_user.id,
    )


# ==========================================================
# Reports List
# ==========================================================

@router.get("/reports")
def reports(
    search: str | None = None,
    patient_id: int | None = None,
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
        search=search,
        patient_id=patient_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Report Detail
# ==========================================================

@router.get("/reports/{report_id}")
def report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("lab:view")
    ),
):
    return get_report_detail(
        db=db,
        report_id=report_id,
    )