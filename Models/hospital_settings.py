from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base

IST = ZoneInfo("Asia/Kolkata")
SETTINGS_ROW_ID = 1


class HospitalSettings(Base):
    __tablename__ = "hospital_settings"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, default="")
    tagline = Column(String(300), nullable=True)
    address_line1 = Column(String(300), nullable=True)
    address_line2 = Column(String(300), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    website = Column(String(300), nullable=True)
    gstin = Column(String(20), nullable=True)
    pan = Column(String(20), nullable=True)
    license_number = Column(String(100), nullable=True)
    default_registration_fee = Column(Float, nullable=False, default=0.0)
    default_consultation_fee = Column(Float, nullable=False, default=0.0)
    default_gst_percent = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="INR")
    timezone = Column(String(64), nullable=False, default="Asia/Kolkata")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
    )
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
