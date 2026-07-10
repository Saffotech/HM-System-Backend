"""Doctor notification APIs."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Enums.notification import NotificationType, SourceModule
from Models.user import User
from Schemas.notification_schema import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from Services import notification_service as service

router = APIRouter(prefix="/doctor/notifications", tags=["Doctor Notifications"])


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("notifications:view")),
):
    return {"count": service.get_unread_count(db, current_user.id)}


@router.patch(
    "/read-all",
    status_code=status.HTTP_200_OK,
)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("notifications:update")),
):
    return service.mark_all_as_read(db, current_user.id)


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
)
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
    is_read: Optional[bool] = Query(None),
    source_module: Optional[SourceModule] = Query(None),
    notification_type: Optional[NotificationType] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("notifications:view")),
):
    return service.get_notifications(
        db,
        current_user.id,
        page=page,
        limit=limit,
        search=search,
        is_read=is_read,
        source_module=source_module,
        notification_type=notification_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("notifications:update")),
):
    return service.mark_as_read(db, current_user.id, notification_id)
