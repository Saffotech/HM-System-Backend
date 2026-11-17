from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_other_visit_schema import DepartmentListResponse
from Services.nurse_other_visit_service import list_departments_service

router = APIRouter(
    prefix="/nurse/other-visits",
    tags=["Nurse Other Visits"],
)


@router.get(
    "/departments",
    response_model=DepartmentListResponse,
)
def list_departments(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_other_visits:view")),
):
    return list_departments_service(
        db,
        search=search,
        page=page,
        page_size=page_size,
    )
