from datetime import datetime
from zoneinfo import ZoneInfo
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
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
# VITAL STATUS
# ==========================================================

class VitalStatus(str, enum.Enum):
    RECORDED = "recorded"
    REVIEWED = "reviewed"


# ==========================================================
# PATIENT VITALS
# ==========================================================

class PatientVitals(Base):

    __tablename__ = "patient_vitals"

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

    recorded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # ======================================================
    # VITALS
    # ======================================================

    temperature = Column(
        Float,
        nullable=True
    )

    blood_pressure = Column(
        String(20),
        nullable=True
    )

    heart_rate = Column(
        Integer,
        nullable=True
    )

    respiratory_rate = Column(
        Integer,
        nullable=True
    )

    oxygen_saturation = Column(
        Integer,
        nullable=True
    )

    blood_sugar = Column(
        Float,
        nullable=True
    )

    weight = Column(
        Float,
        nullable=True
    )

    pain_level = Column(
        Integer,
        nullable=True
    )

    observation_notes = Column(
        Text,
        nullable=True
    )

    # ======================================================
    # STATUS
    # ======================================================

    status = Column(
        Enum(VitalStatus),
        nullable=False,
        default=VitalStatus.RECORDED,
        index=True
    )

    # ======================================================
    # AUDIT FIELDS
    # ======================================================

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

    recorded_at = Column(
        DateTime(timezone=True),
        default=_now,
        index=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    appointment = relationship(
        "Appointment"
    )

    patient = relationship(
        "Patient"
    )

    nurse = relationship(
        "User",
        foreign_keys=[recorded_by]
    )