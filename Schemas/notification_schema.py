from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    message: Optional[str] = None
    notification_type: NotificationType
    priority: NotificationPriority
    source_module: SourceModule
    reference_type: ReferenceType
    reference_id: int
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[NotificationResponse]


class UnreadCountResponse(BaseModel):
    count: int
