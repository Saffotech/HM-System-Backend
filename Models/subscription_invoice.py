"""Platform subscription invoices. These are not hospital OPD bills."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base

IST = ZoneInfo("Asia/Kolkata")


def _now():
    return datetime.now(IST)


class SubscriptionInvoice(Base):
    __tablename__ = "subscription_invoices"

    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_date", name="uq_subscription_invoice_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(30), unique=True, nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    plan = Column(String(50), nullable=False)
    billing_cycle = Column(String(20), nullable=False)
    amount = Column(Integer, nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="Pending", index=True)
    method = Column(String(30), nullable=True)
    reference = Column(String(100), nullable=True)
    paid_at = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    payment_amount = Column(Integer, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    hospital = relationship("Tenant", foreign_keys=[tenant_id])
    recorder = relationship("User", foreign_keys=[recorded_by])
