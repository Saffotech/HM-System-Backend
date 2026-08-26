from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder

from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Services.doctor_patient_queue_service import get_today_queue_service
from Services.doctor_helpers import with_nurse_names
from Utils.pagination import paginate_sequence


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
    page: int | None = Query(
        None,
        ge=1,
        description="Optional page. Omit to return the full queue (legacy clients).",
    ),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description="Optional page size when page is provided.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    queue = get_today_queue_service(
        db=db,
        doctor_id=current_user.id,
    )
    items, total, page_n, size = paginate_sequence(
        queue, page=page, page_size=page_size
    )
    payload = {
        "success": True,
        "total_queue": total,
        "queue": with_nurse_names(db, jsonable_encoder(items)),
    }
    if page is not None:
        payload["page"] = page_n
        payload["page_size"] = size
        payload["total"] = total
    return payload
