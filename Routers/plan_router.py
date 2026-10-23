from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Services.plan_service import list_plans
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/platform/plans", tags=["Subscription Plans"])


@router.get("")
def read_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_plans(db, current_user)
