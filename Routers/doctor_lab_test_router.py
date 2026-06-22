from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from sqlalchemy.orm import Session

from database import get_db

from Models.user import User

from Schemas.doctor_lab_test_schema import (
    LabTestCreate,
    LabTestUpdate,
    LabTestResponse,
    LabTestListPaginatedResponse,
    LabTestDetailResponse,
    DoctorLabReportListResponse,
    DoctorLabReportDetailResponse,
)

from Schemas.lab_schema import ReportSource

from Services.doctor_lab_test_service import (
    create_lab_test_service,
    get_lab_tests_service,
    get_lab_test_by_id_service,
    update_lab_test_service,
    cancel_lab_test_service,
    get_doctor_lab_reports_service,
    get_doctor_lab_report_by_test_service,
    get_doctor_lab_report_file_by_test_service,
)

from dependencies import get_current_user, PermissionChecker


router = APIRouter(
    prefix="/lab-tests",
    tags=["Lab Tests"],
)


# ==========================================================
# Create Lab Test
# ==========================================================

@router.post(
    "",
    response_model=LabTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lab_test(
    payload: LabTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    return create_lab_test_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id,
    )


# ==========================================================
# View All / Search Lab Tests
# ==========================================================

@router.get(
    "",
    response_model=LabTestListPaginatedResponse,
)
def get_lab_tests(
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    return get_lab_tests_service(
        db=db,
        doctor_id=current_user.id,
        search=search,
        patient_id=patient_id,
        patient_uid=patient_uid,
        status=status,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Doctor Lab Report History
# ==========================================================

@router.get(
    "/reports",
    response_model=DoctorLabReportListResponse,
)
def get_doctor_lab_reports(
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    patient_name: str | None = None,
    test_name: str | None = None,
    status: str | None = None,
    source: ReportSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    return get_doctor_lab_reports_service(
        db=db,
        doctor_id=current_user.id,
        search=search,
        patient_id=patient_id,
        patient_uid=patient_uid,
        patient_name=patient_name,
        test_name=test_name,
        status=status,
        source=source,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Lab Test Detail
# ==========================================================

@router.get(
    "/{test_id}",
    response_model=LabTestDetailResponse,
)
def get_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    return get_lab_test_by_id_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id,
    )


# ==========================================================
# Update Lab Test
# ==========================================================

@router.put(
    "/{test_id}",
    response_model=LabTestResponse,
)
def update_lab_test(
    test_id: int,
    payload: LabTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    return update_lab_test_service(
        db=db,
        test_id=test_id,
        payload=payload,
        doctor_id=current_user.id,
    )


# ==========================================================
# Cancel Lab Test
# ==========================================================

@router.patch(
    "/{test_id}/cancel",
)
def cancel_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    return cancel_lab_test_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id,
    )


# ==========================================================
# Doctor View Report (parameters + metadata)
# ==========================================================

@router.get(
    "/{test_id}/report",
    response_model=DoctorLabReportDetailResponse,
)
def get_doctor_lab_report(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    return get_doctor_lab_report_by_test_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id,
    )


# ==========================================================
# Doctor Download Report File
# ==========================================================

@router.get(
    "/{test_id}/report/file",
)
def get_doctor_lab_report_file(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:view")),
):
    return get_doctor_lab_report_file_by_test_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id,
    )
