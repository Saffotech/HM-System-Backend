from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Schemas.doctor_prescription_schema import (
    PrescriptionCreate,
    PrescriptionResponse,
    PrescriptionListPaginatedResponse,
)
from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit
from Services.doctor_prescription_service import (
    create_prescription_service,
    get_prescription_by_id_service,
    get_patient_prescriptions_service,
    update_prescription_service,
)

router = APIRouter(
    prefix="/prescriptions",
    tags=["Doctor Prescriptions"],
)


# ==========================================================
# Create Prescription
# ==========================================================

@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prescription(
    prescription_data: PrescriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:create")),
):
    prescription = create_prescription_service(
        db=db,
        prescription_data=prescription_data,
        doctor_id=current_user.id,
    )
    doctor_audit.log_prescription_create(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        payload=prescription_data,
        prescription_id=prescription.id,
    )
    return prescription


# ==========================================================
# Get Prescription By ID
# ==========================================================

@router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
)
def get_prescription_by_id(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prescription = get_prescription_by_id_service(
        db=db,
        prescription_id=prescription_id,
        doctor_id=current_user.id,
    )
    doctor_audit.log_prescription_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        prescription_id=prescription_id,
    )

    return prescription


# ==========================================================
# Get Patient Prescriptions
# ==========================================================

@router.get(
    "/patient/{patient_id}",
    response_model=PrescriptionListPaginatedResponse,
    status_code=status.HTTP_200_OK,
)
def get_patient_prescriptions(
    patient_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_patient_prescriptions_service(
        db=db,
        patient_id=patient_id,
        doctor_id=current_user.id,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Update Prescription
# ==========================================================

@router.put(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
)
def update_prescription(
    prescription_id: int,
    prescription_data: PrescriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("prescriptions:update")),
):
    prescription = update_prescription_service(
        db=db,
        prescription_id=prescription_id,
        prescription_data=prescription_data,
        doctor_id=current_user.id,
    )
    doctor_audit.log_prescription_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        prescription_id=prescription_id,
        payload=prescription_data,
    )
    return prescription
