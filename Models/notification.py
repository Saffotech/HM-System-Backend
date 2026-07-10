from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from Enums.notification import (
    NotificationPriority,
    NotificationType,
    ReferenceType,
    SourceModule,
)
from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)

    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    priority = Column(
        Enum(NotificationPriority),
        nullable=False,
        default=NotificationPriority.NORMAL,
        index=True,
    )
    source_module = Column(Enum(SourceModule), nullable=False, index=True)
    reference_type = Column(Enum(ReferenceType), nullable=False)
    reference_id = Column(Integer, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_name = Column(String(255), nullable=True)

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    recipient = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )
