from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.doctor_consultation_schema import (
    ConsultationContextResponse,
    SaveConsultationRequest,
    SaveConsultationResponse,
)
from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    result = get_consultation_context_service(
        db=db,
        appointment_id=appointment_id,
        doctor_id=current_user.id,
    )
    doctor_audit.log_consultation_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        appointment_id=appointment_id,
    )
    return result


@router.post(
    "/save",
    response_model=SaveConsultationResponse,
    status_code=status.HTTP_200_OK,
)
def save_consultation(
    payload: SaveConsultationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    result = save_consultation_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id,
    )
    doctor_audit.log_consultation_save(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        payload=payload,
        result=result,
    )
    return result
