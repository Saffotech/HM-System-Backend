"""OPD billing extensions: payments ledger, bill line items, appointments, beds."""
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from zoneinfo import ZoneInfo

from database import Base
from Models.tenant import TenantScoped


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle — same shape as queue (no waiting/in_progress)."""

    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class BillItem(TenantScoped):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("opd_visits.id"), nullable=False, index=True)
    description = Column(String, nullable=False)
    qty = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)


class PaymentTransaction(TenantScoped):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("opd_visits.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_mode = Column(String, nullable=False)
    transaction_reference = Column(String, nullable=True)
    paid_at = Column(DateTime(timezone=True), default=_now)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class Appointment(TenantScoped):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_scheduled_at_status", "scheduled_at", "status"),
        UniqueConstraint(
            "tenant_id",
            "appointment_uid",
            name="uq_appointments_tenant_uid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    appointment_uid = Column(String, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    symptoms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)
    appointment_type = Column(String, default="opd")  # opd / follow-up
    status = Column(
        Enum(
            AppointmentStatus,
            name="appointmentstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AppointmentStatus.scheduled,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)


class Bed(TenantScoped):
    __tablename__ = "beds"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "ward_name",
            "bed_number",
            name="uq_beds_tenant_ward_number",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    bed_number = Column(String, nullable=False)
    ward_name = Column(String, nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    status = Column(String, default="available")  # available / occupied
    bed_type = Column(String, nullable=False, default="single")  # single / double
    admitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
