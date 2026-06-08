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
    Enum,
    Boolean
)

from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


# ==========================================================
# STATUS
# ==========================================================

class MedicationStatus(str, enum.Enum):
    GIVEN = "given"
    REFUSED = "refused"
    MISSED = "missed"
    DELAYED = "delayed"


# ==========================================================
# MEDICATION ADMINISTRATION
# ==========================================================

class MedicationAdministration(Base):

    __tablename__ = "medication_administrations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    prescription_item_id = Column(
        Integer,
        ForeignKey("prescription_items.id"),
        nullable=False,
        index=True
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    administered_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Snapshot Fields

    medicine_name = Column(
        String(255),
        nullable=False
    )

    dosage = Column(
        String(100),
        nullable=True
    )

    frequency = Column(
        String(100),
        nullable=True
    )

    bed_number = Column(
        String(50),
        nullable=True
    )

    ward_name = Column(
        String(100),
        nullable=True
    )

    scheduled_time = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    status = Column(
        Enum(MedicationStatus),
        nullable=False,
        index=True
    )

    remarks = Column(
        Text,
        nullable=True
    )

    administered_at = Column(
        DateTime(timezone=True),
        default=_now,
        index=True
    )

    is_active = Column(Boolean, default=True)

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

    prescription_item = relationship(
        "PrescriptionItem",
        back_populates="administrations"
    )

    patient = relationship(
        "Patient"
    )

    nurse = relationship(
        "User",
        foreign_keys=[administered_by]
    )

    created_by_user = relationship(
        "User",
        foreign_keys=[created_by]
    )

    updated_by_user = relationship(
        "User",
        foreign_keys=[updated_by]
    )