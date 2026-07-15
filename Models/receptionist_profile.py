"""Receptionist professional profile (1:1 with users)."""
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
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class ReceptionistProfile(Base):
    __tablename__ = "receptionist_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    employee_id = Column(String(50), nullable=True, unique=True)
    qualification = Column(String(255), nullable=True)
    experience_years = Column(Integer, nullable=True)
    joining_date = Column(Date, nullable=True)
    bio = Column(Text, nullable=True)
    languages = Column(JSONB, nullable=False, server_default="[]")
    profile_image = Column(String(500), nullable=True)
    is_profile_completed = Column(Boolean, nullable=False, default=False)

    # Admin-owned shift
    shift_name = Column(String(100), nullable=True)
    shift_start_time = Column(Time, nullable=True)
    shift_end_time = Column(Time, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    user = relationship("User", back_populates="receptionist_profile")
