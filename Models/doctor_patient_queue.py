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
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, String as SAString

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


# ==========================================================
# QUEUE STATUS
# ==========================================================

class QueueStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
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


class LowercaseStrEnum(TypeDecorator):
    """Store str Enum values on VARCHAR; accept legacy UPPERCASE DB rows."""

    impl = SAString
    cache_ok = True

    def __init__(self, enum_cls, length: int = 32):
        self.enum_cls = enum_cls
        super().__init__(length)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        return self.enum_cls(str(value).strip().lower()).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value
        return self.enum_cls(str(value).strip().lower())


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
        LowercaseStrEnum(QueueStatus, length=32),
        nullable=False,
        default=QueueStatus.SCHEDULED,
    )

    priority = Column(
        LowercaseStrEnum(QueuePriority, length=32),
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