from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB

from database import Base

IST = ZoneInfo("Asia/Kolkata")
OPD_SETTINGS_ROW_ID = 1


class OpdSettings(Base):
    """Singleton hospital OPD operational settings (Admin-controlled)."""

    __tablename__ = "opd_settings"

    id = Column(Integer, primary_key=True)
    allow_patient_delete = Column(Boolean, nullable=False, default=True)
    allow_appointment_delete = Column(Boolean, nullable=False, default=True)
    allow_unpaid_bill_delete = Column(Boolean, nullable=False, default=True)
    require_admin_approval_for_delete = Column(Boolean, nullable=False, default=True)
    # Reserved for future OPD controls (pricing, slots, payment modes, etc.)
    extra = Column(JSONB, nullable=False, server_default="{}")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
    )
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
