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
    Date,
    Time,
    Enum,
    Boolean,
    UniqueConstraint
)

from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


# ==========================================================
# HANDOVER STATUS
# ==========================================================

class HandoverStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"


# ==========================================================
# SHIFT HANDOVER
# ==========================================================

class ShiftHandover(Base):

    __tablename__ = "shift_handovers"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    handover_uid = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    outgoing_nurse_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    replacement_nurse_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True,
        index=True
    )

    ward_name = Column(
        String(150),
        nullable=False,
        index=True
    )

    shift_date = Column(
        Date,
        nullable=False,
        index=True
    )

    shift_start = Column(
        Time,
        nullable=True
    )

    shift_end = Column(
        Time,
        nullable=True
    )

    general_notes = Column(
        Text,
        nullable=True
    )

    status = Column(
        Enum(HandoverStatus),
        nullable=False,
        default=HandoverStatus.PENDING,
        index=True
    )

    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    taken_over_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    take_over_notes = Column(
        Text,
        nullable=True
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

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    outgoing_nurse = relationship(
        "User",
        foreign_keys=[outgoing_nurse_id]
    )

    replacement_nurse = relationship(
        "User",
        foreign_keys=[replacement_nurse_id]
    )

    patients = relationship(
        "ShiftHandoverPatient",
        back_populates="handover",
        cascade="all, delete-orphan"
    )


# ==========================================================
# SHIFT HANDOVER PATIENT
# ==========================================================

class ShiftHandoverPatient(Base):

    __tablename__ = "shift_handover_patients"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    handover_id = Column(
        Integer,
        ForeignKey("shift_handovers.id"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    # Snapshot Fields

    patient_name = Column(
        String(255),
        nullable=False
    )

    bed_number = Column(
        String(50),
        nullable=True
    )

    # Handover Information

    patient_summary = Column(
        String,
        nullable=True
    )

    pending_tasks = Column(
        String,
        nullable=True
    )

    critical_alerts = Column(
        String,
        nullable=True
    )

    medication_pending = Column(
        String,
        nullable=True
    )

    doctor_instructions = Column(
        String,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
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

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    handover = relationship(
        "ShiftHandover",
        back_populates="patients"
    )

    patient = relationship(
        "Patient"
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by]
    )

    updated_by_user = relationship(
        "User",
        foreign_keys=[updated_by]
    )

    # ======================================================
    # CONSTRAINTS
    # ======================================================

    __table_args__ = (
        UniqueConstraint(
            "handover_id",
            "patient_id",
            name="uq_handover_patient"
        ),
    )