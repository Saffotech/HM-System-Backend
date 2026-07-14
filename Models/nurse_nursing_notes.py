from datetime import datetime
from zoneinfo import ZoneInfo
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum
)

from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


# ==========================================================
# NOTE STATUS
# ==========================================================

class NursingNoteStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


# ==========================================================
# NURSING NOTE
# ==========================================================

class NursingNote(Base):

    __tablename__ = "nursing_notes"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=True,
        index=True
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    nurse_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    symptoms = Column(
        Text,
        nullable=True
    )

    treatment_response = Column(
        Text,
        nullable=True
    )

    additional_notes = Column(
        Text,
        nullable=True
    )

    status = Column(
        Enum(NursingNoteStatus),
        nullable=False,
        default=NursingNoteStatus.ACTIVE,
        index=True
    )

    # Audit Fields

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
        default=_now,
        index=True
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

    nurse = relationship(
        "User",
        foreign_keys=[nurse_id]
    )