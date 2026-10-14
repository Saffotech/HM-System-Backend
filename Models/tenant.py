from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from database import Base

IST = ZoneInfo("Asia/Kolkata")


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    hospital_type = Column(String(50), nullable=False, default="General")
    email = Column(String(200), unique=True, nullable=True, index=True)
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST),
    )


class TenantScoped(Base):
    """Hospital-owned row. tenant_id is the hospital."""

    __abstract__ = True

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)