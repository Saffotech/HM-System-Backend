from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.doctor_appointment_schema import AppointmentConsultationUpdate
from Schemas.doctor_consultation_schema import (
    ConsultationContextResponse,
    SaveConsultationRequest,
    SaveConsultationResponse,
)
from Services.doctor_appointment_service import complete_appointment_consultation_service
from Services.doctor_consultation_service import (
    get_consultation_context_service,
    save_consultation_service,
)

router = APIRouter(
    prefix="/consultations",
    tags=["Doctor Consultations"],
)


@router.get(
    "/appointment/{appointment_id}",
    response_model=ConsultationContextResponse,
    status_code=status.HTTP_200_OK,
)
def get_consultation_context(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return get_consultation_context_service(
        db=db,
        appointment_id=appointment_id,
        doctor_id=current_user.id,
    )


@router.post(
    "/save",
    response_model=SaveConsultationResponse,
    status_code=status.HTTP_200_OK,
)
def save_consultation(
    payload: SaveConsultationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    return save_consultation_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id,
    )


@router.patch(
    "/appointment/{appointment_id}",
    status_code=status.HTTP_200_OK,
)
def patch_appointment_consultation(
    appointment_id: int,
    clinical: AppointmentConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    return complete_appointment_consultation_service(
        db=db,
        appointment_id=appointment_id,
        doctor_id=current_user.id,
        clinical=clinical,
    )
