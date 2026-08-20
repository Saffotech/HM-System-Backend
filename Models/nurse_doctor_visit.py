"""Nurse-logged doctor visit records (operational tracking, not IPD billing)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class NurseDoctorVisit(Base):
    __tablename__ = "nurse_doctor_visits"

    id = Column(Integer, primary_key=True, index=True)

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    doctor_name = Column(String(255), nullable=False)

    visited_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        index=True,
    )

    notes = Column(Text, nullable=True)

    recorded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    recorded_by_name = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )

    updated_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    updated_by_name = Column(String(255), nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_voided = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    voided_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    voided_by_name = Column(String(255), nullable=True)

    voided_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    void_reason = Column(Text, nullable=True)

    patient = relationship("Patient", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])
    recorder = relationship("User", foreign_keys=[recorded_by])
