from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    )


# ==========================================================
# PRESCRIPTION
# ==========================================================

class Prescription(Base):

    __tablename__ = "prescriptions"
    __table_args__ = (
        CheckConstraint(
            "(appointment_id IS NOT NULL AND admission_id IS NULL) OR "
            "(appointment_id IS NULL AND admission_id IS NOT NULL)",
            name="ck_prescriptions_one_parent",
        ),
        Index(
            "uq_prescriptions_appointment_id",
            "appointment_id",
            unique=True,
            postgresql_where=text("appointment_id IS NOT NULL"),
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id"),
        nullable=True,
        index=True,
    )

    admission_id = Column(
        Integer,
        ForeignKey("ipd_admissions.id"),
        nullable=True,
        index=True,
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    patient_name = Column(
        String(255),
        nullable=False
    )

    doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    diagnosis = Column(
        Text,
        nullable=False
    )

    notes = Column(
        Text,
        nullable=True
    )
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
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
        default=_now
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now
    )

    # Relationships

    appointment = relationship(
        "Appointment",
        foreign_keys=[appointment_id],
    )

    admission = relationship(
        "IpdAdmission",
        foreign_keys=[admission_id],
    )

    patient = relationship(
        "Patient"
    )

    doctor = relationship(
        "User",
        foreign_keys=[doctor_id]
    )

    items = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan"
    )


# ==========================================================
# PRESCRIPTION ITEM
# ==========================================================

class PrescriptionItem(Base):

    __tablename__ = "prescription_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    prescription_id = Column(
        Integer,
        ForeignKey("prescriptions.id"),
        nullable=False,
        index=True
    )

    medicine_name = Column(
        String(255),
        nullable=False
    )

    dosage = Column(
        String(100),
        nullable=False
    )

    frequency = Column(
        String(50),
        nullable=False
    )

    duration = Column(
        String(50),
        nullable=False
    )

    instructions = Column(
        Text,
        nullable=True
    )

    # Optional medicine details (old clients omit these; columns are nullable)
    form = Column(
        String(50),
        nullable=True
    )
    dose = Column(
        String(50),
        nullable=True
    )
    route = Column(
        String(50),
        nullable=True
    )
    timing = Column(
        String(50),
        nullable=True
    )
    quantity = Column(
        Integer,
        nullable=True
    )
    quantity_unit = Column(
        String(50),
        nullable=True
    )

    # Medication Schedule

    start_date = Column(
        Date,
        nullable=True
    )

    end_date = Column(
        Date,
        nullable=True
    )

    schedule_time = Column(
        Time,
        nullable=True
    )

    dose_schedule = Column(
        String(255),
        nullable=True
    )
    # Example:
    # 08:00,14:00,20:00

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

    prescription = relationship(
        "Prescription",
        back_populates="items"
    )

    administrations = relationship(
        "MedicationAdministration",
        back_populates="prescription_item",
        cascade="all, delete-orphan"
    )