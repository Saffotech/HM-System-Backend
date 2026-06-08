from fastapi import (
    APIRouter,
    Depends,
    Query
)

from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user
)

from Models.user import User

from Services.nurse_today_queue_service import (
    get_nurse_today_queue_service
)

router = APIRouter(
    prefix="/nurse",
    tags=["Nurse Queue"]
)


# ==========================================================
# TODAY'S QUEUE
# ==========================================================

@router.get("/queue/today")
def get_today_queue(

    search: str | None = Query(
        None,
        description="Search by Name, UHID, Phone, Appointment UID, Patient ID or Token Number"
    ),

    status: str | None = Query(
        None,
        description="waiting, vitals_completed, in_progress, completed"
    ),

    doctor_id: int | None = Query(
        None,
        ge=1
    ),

    priority: str | None = Query(
        None
    ),

    page: int = Query(
        1,
        ge=1
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    return get_nurse_today_queue_service(
        db=db,

        search=search,

        status=status,
        doctor_id=doctor_id,
        priority=priority,

        page=page,
        page_size=page_size
    )