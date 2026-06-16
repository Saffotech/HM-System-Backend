from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo
import enum


class LabTestStatus(str, enum.Enum):
    ORDERED = "ordered"
    SAMPLE_COLLECTED = "sample_collected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LabTestOrder(Base):

    __tablename__ = "lab_test_orders"

    id = Column(Integer, primary_key=True, index=True)

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    patient_name = Column(
        String(255),
        nullable=False,
        index=True
    )

    patient_uhid = Column(
        String(100),
        nullable=False,
        index=True
    )

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    test_name = Column(
        String(255),
        nullable=False
    )

    category = Column(
        String(100),
        nullable=False
    )

    priority = Column(
        String(50),
        nullable=False,
        default="Normal"
    )

    clinical_notes = Column(
        String(500),
        nullable=True
    )

    status = Column(
        Enum(LabTestStatus),
        nullable=False,
        default=LabTestStatus.ORDERED
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

    # Relationships
    appointment = relationship(
        "Appointment",
        foreign_keys=[appointment_id]
    )

    doctor = relationship(
        "User",
        foreign_keys=[doctor_id]
    )

    lab_result = relationship(
        "LabResult",
        back_populates="lab_order",
        uselist=False,
    )