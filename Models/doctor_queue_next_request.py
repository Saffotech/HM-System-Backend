from datetime import date, datetime
import enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from zoneinfo import ZoneInfo

from database import Base

IST = ZoneInfo("Asia/Kolkata")


class NextRequestStatus(str, enum.Enum):
    pending = "pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


def _now():
    return datetime.now(IST)


class DoctorQueueNextRequest(Base):
    """Doctor 'Next' button → receptionist notification (one pending per doctor per day)."""

    __tablename__ = "doctor_queue_next_requests"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    queue_id = Column(Integer, ForeignKey("patient_queue.id"), nullable=True, index=True)
    status = Column(
        String,
        default=NextRequestStatus.pending.value,
        nullable=False,
    )
    request_date = Column(Date, nullable=False, index=True)
    requested_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    handled_at = Column(DateTime(timezone=True), nullable=True)
    handled_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    queue = relationship("PatientQueue", foreign_keys=[queue_id])
