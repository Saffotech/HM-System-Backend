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

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    patient_id = Column(
        Integer,
        nullable=False
    )

    patient_name = Column(
        String,
        nullable=False
    )

    patient_uhid = Column(
        String,
        nullable=False
    )

    patient_phone = Column(
        String,
        nullable=False
    )

    patient_age = Column(
        Integer,
        nullable=True
    )

    patient_gender = Column(
        String,
        nullable=True
    )

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    appointment_date = Column(
        Date,
        nullable=False
    )

    appointment_time = Column(
        Time,
        nullable=False
    )

    appointment_type = Column(
        String,
        default="new",
        nullable=False
    )

    priority = Column(
        String,
        default="normal",
        nullable=False
    )

    status = Column(
        String,
        default="scheduled",
        nullable=False
    )

    reason = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    checked_in_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    consultation_started_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    consultation_completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

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

    doctor = relationship(
        "User",
        foreign_keys=[doctor_id]
    )