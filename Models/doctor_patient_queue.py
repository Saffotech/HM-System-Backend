from datetime import datetime
from zoneinfo import ZoneInfo
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )
 

# ==========================================================
# QUEUE STATUS
# ==========================================================

class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    VITALS_COMPLETED = "vitals_completed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# ==========================================================
# PRIORITY
# ==========================================================

class QueuePriority(str, enum.Enum):
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"


# ==========================================================
# PATIENT QUEUE
# ==========================================================

class PatientQueue(Base):

    __tablename__ = "patient_queue"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
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

    patient_phone = Column(
        String(20),
        nullable=True
    )

    appointment_uid = Column(
        String(100),
        nullable=True,
        index=True
    )

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    token_number = Column(
        Integer,
        nullable=False,
        index=True
    )

    queue_date = Column(
        Date,
        nullable=False,
        index=True
    )

    status = Column(
        Enum(
            QueueStatus,
            name="queuestatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=QueueStatus.WAITING,
    )

    priority = Column(
        Enum(
            QueuePriority,
            name="queuepriority",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=QueuePriority.NORMAL,
    )

    is_current = Column(
        Boolean,
        default=False
    )

    queue_entered_at = Column(
        DateTime(timezone=True),
        default=_now
    )

    consultation_started_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    consultation_completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    updated_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=_now
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now
    )

    # Relationships

    appointment = relationship(
        "Appointment"
    )

    patient = relationship(
        "Patient"
    )

    doctor = relationship(
        "User",
        foreign_keys=[doctor_id],
    )  