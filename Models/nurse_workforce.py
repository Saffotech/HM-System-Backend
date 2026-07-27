"""Nurse workforce — shift master and roster."""
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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class NurseWorkforceShift(Base):
    """Shift master — Morning/Evening/Night/custom templates."""

    __tablename__ = "nurse_workforce_shifts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(50), nullable=True, unique=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    grace_minutes = Column(Integer, nullable=False, default=15)
    color = Column(String(20), nullable=True, default="#3B82F6")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_template = Column(Boolean, nullable=False, default=False)
    weekly_mask = Column(String(20), nullable=True, default="1111100")  # Mon–Sun
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class NurseWorkforceRoster(Base):
    """Monthly/daily nurse roster assignment."""

    __tablename__ = "nurse_workforce_rosters"
    __table_args__ = (
        UniqueConstraint(
            "nurse_id",
            "roster_date",
            "shift_id",
            name="uq_nurse_roster_date_shift",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    nurse_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    shift_id = Column(
        Integer, ForeignKey("nurse_workforce_shifts.id"), nullable=False, index=True
    )
    department_id = Column(
        Integer, ForeignKey("departments.id"), nullable=True, index=True
    )
    roster_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="scheduled", index=True)
    # scheduled | confirmed | cancelled | completed
    notes = Column(Text, nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    nurse = relationship("User", foreign_keys=[nurse_id])
    shift = relationship("NurseWorkforceShift", foreign_keys=[shift_id])
    department = relationship("Department", foreign_keys=[department_id])
    assigner = relationship("User", foreign_keys=[assigned_by])
