"""Super Admin professional profile (1:1 with users) — lightweight identity."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class SuperAdminProfile(Base):
    __tablename__ = "super_admin_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    employee_id = Column(String(50), nullable=True, unique=True)
    joining_date = Column(Date, nullable=True)
    bio = Column(Text, nullable=True)
    languages = Column(JSONB, nullable=False, server_default="[]")
    profile_image = Column(String(500), nullable=True)
    is_profile_completed = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    user = relationship("User", back_populates="super_admin_profile")
