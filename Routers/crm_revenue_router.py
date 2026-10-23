from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Services.crm_revenue_service import crm_revenue
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/crm/revenue", tags=["CRM Revenue"])


@router.get("")
def read_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return crm_revenue(db, current_user)
