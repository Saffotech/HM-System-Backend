"""Doctor weekly schedules and leave / holiday blocks."""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    Time,
)
from zoneinfo import ZoneInfo

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class DoctorLeaveType(str, enum.Enum):
    leave = "leave"
    holiday = "holiday"


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)  # 0=Monday … 6=Sunday
    shift_start = Column(Time, nullable=False)
    shift_end = Column(Time, nullable=False)
    consultation_duration_minutes = Column(Integer, nullable=False, default=15)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    leave_type = Column(
        Enum(DoctorLeaveType, name="doctorleavetype"),
        nullable=False,
    )
    reason = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
