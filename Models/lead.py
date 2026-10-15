"""Platform CRM leads. These rows are not hospital-owned, so they are not tenant-scoped."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base

IST = ZoneInfo("Asia/Kolkata")


def _now():
    return datetime.now(IST)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    hospital_name = Column(String(200), nullable=False, index=True)
    hospital_type = Column(String(50), nullable=False, default="General")
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    hospital_email = Column(String(200), nullable=True)
    contact_person = Column(String(200), nullable=False)
    designation = Column(String(120), nullable=True)
    contact_phone = Column(String(30), nullable=False)
    contact_email = Column(String(200), nullable=True)
    source = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False, default="Medium")
    plan = Column(String(50), nullable=True)
    billing_cycle = Column(String(20), nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="New", index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    follow_up_date = Column(Date, nullable=True)
    next_action = Column(String(200), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    agreed_at = Column(DateTime(timezone=True), nullable=True)
    agreed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    handover_note = Column(Text, nullable=True)
    close_reason = Column(String(100), nullable=True)
    close_note = Column(Text, nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    hospital_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    registered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
    agreed_by_user = relationship("User", foreign_keys=[agreed_by])
    closed_by_user = relationship("User", foreign_keys=[closed_by])
    registered_by_user = relationship("User", foreign_keys=[registered_by])
    activities = relationship(
        "LeadActivity",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadActivity.created_at.desc()",
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    method = Column(String(50), nullable=False)
    note = Column(Text, nullable=False, default="")
    follow_up_date = Column(Date, nullable=True)
    next_action = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    lead = relationship("Lead", back_populates="activities")
    actor = relationship("User", foreign_keys=[actor_id])


def ensure_activity_history_columns(bind) -> None:
    """Add history columns on databases created before follow-up dates were stored."""
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if "lead_activities" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("lead_activities")}
    statements = []
    if "follow_up_date" not in columns:
        statements.append("ALTER TABLE lead_activities ADD COLUMN follow_up_date DATE")
    if "next_action" not in columns:
        statements.append("ALTER TABLE lead_activities ADD COLUMN next_action VARCHAR(200)")
    if not statements:
        return
    with bind.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
