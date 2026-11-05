"""One Legal and Finance case for one agreed hospital lead."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base

IST = ZoneInfo("Asia/Kolkata")


def _now():
    return datetime.now(IST)


class LegalCase(Base):
    __tablename__ = "legal_cases"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, unique=True, index=True)
    hospital_name = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    plan = Column(String(50), nullable=True)
    status = Column(String(40), nullable=False, default="New from CRM", index=True)
    decision_reason = Column(Text, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    advance_received = Column(Boolean, nullable=False, default=False)
    advance_received_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    advance_received_at = Column(DateTime(timezone=True), nullable=True)
    discount = Column(Integer, nullable=False, default=0)
    escalation = Column(String(30), nullable=False, default="Not needed")
    escalation_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    escalation_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    lead = relationship("Lead", foreign_keys=[lead_id])
    documents = relationship("LegalDocument", back_populates="case", cascade="all, delete-orphan")
    checklist = relationship("LegalChecklistItem", back_populates="case", cascade="all, delete-orphan")
    finance = relationship("LegalFinanceTerms", back_populates="case", uselist=False, cascade="all, delete-orphan")
    decision = relationship("LegalCaseDecision", back_populates="case", uselist=False, cascade="all, delete-orphan")


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False, index=True)
    category = Column(String(80), nullable=False)
    file_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    status = Column(String(40), nullable=False, default="Pending Review")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    case = relationship("LegalCase", back_populates="documents")


class LegalChecklistItem(Base):
    __tablename__ = "legal_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    status = Column(String(40), nullable=False, default="Pending")
    note = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("LegalCase", back_populates="checklist")


class LegalFinanceTerms(Base):
    """Price terms for one case. Amounts are whole rupees."""

    __tablename__ = "legal_finance_terms"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False, unique=True, index=True)
    standard_price = Column(Integer, nullable=False, default=0)
    discount = Column(Integer, nullable=False, default=0)
    years = Column(Integer, nullable=False, default=1)
    implementation_fee = Column(Integer, nullable=False, default=0)
    training_fee = Column(Integer, nullable=False, default=0)
    tax_percent = Column(Integer, nullable=False, default=0)
    advance_percent = Column(Integer, nullable=False, default=0)
    credit_days = Column(Integer, nullable=False, default=0)
    frequency = Column(String(20), nullable=False, default="Annual")
    modules = Column(String(200), nullable=True)
    gstin = Column(String(20), nullable=True)
    po_required = Column(String(3), nullable=False, default="No")
    invoice_email = Column(String(200), nullable=True)
    reviewed = Column(Boolean, nullable=False, default=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("LegalCase", back_populates="finance")


class LegalCaseDecision(Base):
    """The current Legal and Finance decision for one case."""

    __tablename__ = "legal_case_decisions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False, unique=True, index=True)
    status = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    condition = Column(Text, nullable=True)
    condition_owner = Column(String(40), nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    case = relationship("LegalCase", back_populates="decision")


def ensure_legal_case_columns(bind) -> None:
    """Add price columns on databases created before the review rules."""
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if "legal_cases" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("legal_cases")}
    statements = []
    if "hospital_name" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN hospital_name VARCHAR(200)")
    if "city" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN city VARCHAR(100)")
    if "plan" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN plan VARCHAR(50)")
    if "discount" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN discount INTEGER NOT NULL DEFAULT 0")
    if "escalation" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN escalation VARCHAR(30) NOT NULL DEFAULT 'Not needed'")
    if "escalation_by" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN escalation_by INTEGER")
    if "escalation_at" not in columns:
        statements.append("ALTER TABLE legal_cases ADD COLUMN escalation_at TIMESTAMP")
    for table, additions in (
        ("legal_documents", (
            ("reviewed_by", "INTEGER"),
            ("reviewed_at", "TIMESTAMP"),
        )),
        ("legal_checklist_items", (
            ("updated_by", "INTEGER"),
            ("updated_at", "TIMESTAMP"),
        )),
        ("legal_finance_terms", (
            ("updated_by", "INTEGER"),
            ("updated_at", "TIMESTAMP"),
        )),
    ):
        if table not in inspector.get_table_names():
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in additions:
            if name not in existing:
                statements.append(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    if not statements:
        return
    with bind.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
