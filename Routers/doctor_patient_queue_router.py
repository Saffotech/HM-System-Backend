from fastapi import APIRouter, Body, Depends, status

from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user,PermissionChecker
from Models.user import User
from Schemas.doctor_consultation_schema import SaveConsultationRequest, SaveConsultationResponse
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema
from Services import doctor_helpers as h
from Services.doctor_patient_queue_service import (
    get_today_queue_service,
    complete_consultation_service,
)
from Services.doctor_consultation_service import save_consultation_service


router = APIRouter(
    prefix="/queue",
    tags=["Doctor Patient Queue"])

# ==========================================================
# Get Today's Queue
# ==========================================================

@router.get("/today",
    status_code=status.HTTP_200_OK
)
def get_today_queue(

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):

    queue = get_today_queue_service(
        db=db,
        doctor_id=current_user.id
    )

    return {
        "success": True,
        "total_queue": len(queue),
        "queue": queue
    }

# ==========================================================
# Complete Consultation
# ==========================================================

@router.put(
    "/complete",
    response_model=SaveConsultationResponse,
    status_code=status.HTTP_200_OK,
)
def complete_consultation_by_appointment(
    payload: SaveConsultationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    """
    Atomic save by ``appointment_id``: ensure queue row, persist clinical fields,
  mark appointment and queue completed (from scheduled).
    """
    return save_consultation_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id,
    )


@router.put("/complete/{queue_id}",
    status_code=status.HTTP_200_OK
)
def complete_consultation(

    queue_id: int,
    clinical: CompleteConsultationSchema | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update"))
):
    """Complete an existing queue visit by ``queue_id`` and persist optional clinical fields."""

    result = complete_consultation_service(
        db=db,
        queue_id=queue_id,
        doctor_id=current_user.id,
        clinical=clinical,
    )

    return {
        "success": True,
        "message": (
            "Consultation completed successfully"
        ),
        "consultation_minutes": result["consultation_minutes"],
        "queue": result["queue"],
        "appointment": h.appointment_to_dict(db, result["appointment"])
        if result.get("appointment")
        else None,
    }
