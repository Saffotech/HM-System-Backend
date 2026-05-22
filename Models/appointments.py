from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Time,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from database import Base

from datetime import datetime
from zoneinfo import ZoneInfo


class Appointment(Base):

    __tablename__ = "appointments"

    # ======================================================
    # Primary Key
    # ======================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ======================================================
    # Patient Information
    # ======================================================

    patient_id = Column(
        Integer,
        nullable=False
    )

    patient_name = Column(
        String,
        nullable=False
    )

    # ======================================================
    # Doctor Information
    # ======================================================

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # ======================================================
    # Appointment Schedule
    # ======================================================

    appointment_date = Column(
        Date,
        nullable=False
    )

    appointment_time = Column(
        Time,
        nullable=False
    )

    # ======================================================
    # Appointment Status
    # ======================================================

    status = Column(
        String,
        default="scheduled",
        nullable=False
    )

    # ======================================================
    # Medical Information
    # ======================================================

    reason = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    # ======================================================
    # Audit Fields
    # ======================================================

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        ),
        onupdate=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    # ======================================================
    # Relationships
    # ======================================================

    doctor = relationship(
        "User",
        foreign_keys=[doctor_id]
    )