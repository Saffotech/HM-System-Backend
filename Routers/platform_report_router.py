from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Services.platform_report_service import crm_analytics, crm_performance, revenue_report
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/platform", tags=["Platform Reports"])


@router.get("/revenue")
def read_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return revenue_report(db, current_user)


@router.get("/crm/performance")
def read_crm_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crm_performance(db, current_user)


@router.get("/crm/analytics")
def read_crm_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crm_analytics(db, current_user)
