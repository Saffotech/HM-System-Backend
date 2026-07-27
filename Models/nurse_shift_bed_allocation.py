"""Nurse shift bed allocations — responsibility only (not patient ownership)."""
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
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class NurseShiftBedAllocation(Base):
    """Persistent bed responsibility for a nurse until admin changes it.

    Does not modify beds.patient_id or imply patient ownership.
    shift_date = assigned_from; assigned_until set when deactivated/reassigned.
    """

    __tablename__ = "nurse_shift_bed_allocations"

    id = Column(Integer, primary_key=True, index=True)

    nurse_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    bed_id = Column(
        Integer,
        ForeignKey("beds.id"),
        nullable=False,
        index=True,
    )

    shift_date = Column(Date, nullable=False, index=True)  # assigned_from

    assigned_until = Column(Date, nullable=True, index=True)

    shift_name = Column(String(100), nullable=False, index=True)

    shift_start = Column(Time, nullable=True)

    shift_end = Column(Time, nullable=True)

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    assigned_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    nurse = relationship("User", foreign_keys=[nurse_id])
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])
    bed = relationship("Bed", foreign_keys=[bed_id])
    department = relationship("Department", foreign_keys=[department_id])
