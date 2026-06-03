from typing import List
from fastapi import (APIRouter,Depends)
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from Models.user import User
from Schemas.doctor_patient_queue_schema import PatientQueueSchema
from Services.nurse_today_queue_service import  get_nurse_today_queue_service


router = APIRouter(
    prefix="/nurse",
    tags=["Nurse"]
)


# ==========================================================
# Today's Queue
# ==========================================================

@router.get(
    "/queue/today",
    response_model=List[PatientQueueSchema]
)
def get_today_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):

    return get_nurse_today_queue_service(
        db=db
    )