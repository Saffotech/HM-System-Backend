from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.platform_staff_schema import PlatformStaffCreate, PlatformStaffOut
from Services.platform_staff_service import create_platform_staff
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/platform/staff", tags=["Platform Staff"])


@router.post("", response_model=PlatformStaffOut, status_code=201)
def create_staff(
    data: PlatformStaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_platform_staff(db, data, current_user)
