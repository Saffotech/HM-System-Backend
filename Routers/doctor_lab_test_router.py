from fastapi import (
    APIRouter,
    Depends,
    Request,
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
    DoctorLabReportDetailResponse,
)

from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit
from Services.doctor_lab_test_service import (
    create_lab_test_service,
    get_lab_tests_service,
    update_lab_test_service,
    cancel_lab_test_service,
    get_doctor_lab_report_by_test_service,
    get_doctor_lab_report_file_by_test_service,
)

from dependencies import get_current_user, PermissionChecker


router = APIRouter(
    prefix="/lab-tests",
    tags=["Doctor Lab Tests Orders"],
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    result = create_lab_test_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id,
    )
    doctor_audit.log_lab_create(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        payload=payload,
        order_id=result.id,
        test_name=result.test_name,
    )
    return result


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
# Update Lab Test
# ==========================================================

@router.put(
    "/{test_id}",
    response_model=LabTestResponse,
)
def update_lab_test(
    test_id: int,
    payload: LabTestUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    result = update_lab_test_service(
        db=db,
        test_id=test_id,
        payload=payload,
        doctor_id=current_user.id,
    )
    doctor_audit.log_lab_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=test_id,
        payload=payload,
        test_name=result.test_name,
    )
    return result


# ==========================================================
# Cancel Lab Test
# ==========================================================

@router.patch(
    "/{test_id}/cancel",
)
def cancel_lab_test(
    test_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab:create")),
):
    result = cancel_lab_test_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id,
    )
    doctor_audit.log_lab_cancel(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        order_id=result.get("order_id", test_id),
        test_name=result.get("test_name"),
    )
    return result


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
