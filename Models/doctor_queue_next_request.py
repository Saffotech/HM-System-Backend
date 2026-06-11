from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from zoneinfo import ZoneInfo

from database import Base

IST = ZoneInfo("Asia/Kolkata")


def _now():
    return datetime.now(IST)


class DoctorQueueNextRequest(Base):
    """Doctor 'Next' button → receptionist notification (one pending per doctor per day)."""

    __tablename__ = "doctor_queue_next_requests"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending | fulfilled | cancelled
    request_date = Column(Date, nullable=False, index=True)
    requested_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    handled_at = Column(DateTime(timezone=True), nullable=True)
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
