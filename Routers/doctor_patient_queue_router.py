from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder

from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Services.doctor_patient_queue_service import get_today_queue_service
from Services.doctor_helpers import with_nurse_names


router = APIRouter(
    prefix="/queue",
    tags=["Doctor Patient Queue"],
)

# ==========================================================
# Get Today's Queue
# ==========================================================

@router.get(
    "/today",
    status_code=status.HTTP_200_OK,
)
def get_today_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    queue = get_today_queue_service(
        db=db,
        doctor_id=current_user.id,
    )

    return {
        "success": True,
        "total_queue": len(queue),
        "queue": with_nurse_names(db, jsonable_encoder(queue)),
    }
