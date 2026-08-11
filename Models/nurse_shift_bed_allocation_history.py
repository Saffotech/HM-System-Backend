"""Immutable history of nurse shift bed allocation changes (Phase 6)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class NurseShiftBedAllocationHistory(Base):
    """Audit trail for allocation create / edit / reassign / activate / deactivate."""

    __tablename__ = "nurse_shift_bed_allocation_history"

    id = Column(Integer, primary_key=True, index=True)

    allocation_id = Column(
        Integer,
        ForeignKey("nurse_shift_bed_allocations.id"),
        nullable=True,
        index=True,
    )

    action = Column(String(50), nullable=False, index=True)
    # created | edited | reassigned | activated | deactivated | deleted

    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    old_nurse_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    new_nurse_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    old_bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True)
    new_bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True)

    shift_date = Column(Date, nullable=True, index=True)
    shift_name = Column(String(100), nullable=True, index=True)

    remarks = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
        index=True,
    )

    allocation = relationship("NurseShiftBedAllocation", foreign_keys=[allocation_id])
    actor = relationship("User", foreign_keys=[actor_id])
    old_nurse = relationship("User", foreign_keys=[old_nurse_id])
    new_nurse = relationship("User", foreign_keys=[new_nurse_id])
    old_bed = relationship("Bed", foreign_keys=[old_bed_id])
    new_bed = relationship("Bed", foreign_keys=[new_bed_id])
