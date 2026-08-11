"""IPD domain: admissions, doctor visits, stay bills, and payments."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class IpdAdmission(Base):
    __tablename__ = "ipd_admissions"

    id = Column(Integer, primary_key=True, index=True)
    admission_no = Column(String, unique=True, nullable=False, index=True)

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    ward_name = Column(String, nullable=True)
    bed_number = Column(String, nullable=True)

    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # admitted | discharged | cancelled
    status = Column(String, nullable=False, default="admitted", index=True)

    admitted_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    discharged_at = Column(DateTime(timezone=True), nullable=True)

    admitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    discharged_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    visits = relationship("IpdDoctorVisit", back_populates="admission", cascade="all, delete-orphan")
    bills = relationship("IpdBill", back_populates="admission", cascade="all, delete-orphan")


class IpdDoctorVisit(Base):
    __tablename__ = "ipd_doctor_visits"

    id = Column(Integer, primary_key=True, index=True)
    admission_id = Column(
        Integer, ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visited_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    charge = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    admission = relationship("IpdAdmission", back_populates="visits")


class IpdBill(Base):
    __tablename__ = "ipd_bills"

    id = Column(Integer, primary_key=True, index=True)
    bill_number = Column(String, unique=True, nullable=False, index=True)
    admission_id = Column(
        Integer, ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    subtotal = Column(Float, nullable=False, default=0.0)
    gst_percent = Column(Float, nullable=False, default=0.0)
    gst_amount = Column(Float, nullable=False, default=0.0)
    grand_total = Column(Float, nullable=False, default=0.0)

    # pending | partial | paid
    payment_status = Column(String, nullable=False, default="pending")
    payment_mode = Column(String, nullable=True)
    paid_amount = Column(Float, nullable=False, default=0.0)
    balance_due = Column(Float, nullable=False, default=0.0)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # draft | final | void
    status = Column(String, nullable=False, default="final")

    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    generated_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    admission = relationship("IpdAdmission", back_populates="bills")
    items = relationship("IpdBillItem", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship(
        "IpdPaymentTransaction", back_populates="bill", cascade="all, delete-orphan"
    )


class IpdBillItem(Base):
    __tablename__ = "ipd_bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(
        Integer, ForeignKey("ipd_bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description = Column(String, nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    # bed | visit | misc
    item_type = Column(String, nullable=False, default="misc")

    bill = relationship("IpdBill", back_populates="items")


class IpdPaymentTransaction(Base):
    __tablename__ = "ipd_payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(
        Integer, ForeignKey("ipd_bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount = Column(Float, nullable=False)
    payment_mode = Column(String, nullable=False)
    transaction_reference = Column(String, nullable=True)
    paid_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    bill = relationship("IpdBill", back_populates="payments")
