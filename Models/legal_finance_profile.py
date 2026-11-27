"""Legal and Finance professional profile. One row per Legal & Finance user."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class LegalFinanceProfile(Base):
    __tablename__ = "legal_finance_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    job_title = Column(String(120), nullable=True)
    profile_image = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    user = relationship("User", back_populates="legal_finance_profile")
