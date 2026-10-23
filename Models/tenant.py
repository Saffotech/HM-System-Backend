from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text

from database import Base

IST = ZoneInfo("Asia/Kolkata")


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    hospital_type = Column(String(50), nullable=False, default="General")
    email = Column(String(200), unique=True, nullable=True, index=True)
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    plan = Column(String(50), nullable=False)
    billing_cycle = Column(String(20), nullable=False)
    trial_period = Column(String(20), nullable=False, default="None")
    tenant_status = Column(String(20), nullable=False, default="Active")
    subscription_status = Column(String(20), nullable=False, default="Active")
    subscription_started_on = Column(Date, nullable=False)
    subscription_renews_on = Column(Date, nullable=False)
    subscription_amount = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST),
    )


def ensure_subscription_columns(bind) -> None:
    """Add subscription columns on databases created before plan registration."""
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if "tenants" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("tenants")}
    statements = []
    additions = (
        ("plan", "VARCHAR(50) NOT NULL DEFAULT 'Professional'"),
        ("billing_cycle", "VARCHAR(20) NOT NULL DEFAULT 'Monthly'"),
        ("trial_period", "VARCHAR(20) NOT NULL DEFAULT 'None'"),
        ("tenant_status", "VARCHAR(20) NOT NULL DEFAULT 'Active'"),
        ("subscription_status", "VARCHAR(20) NOT NULL DEFAULT 'Active'"),
        ("subscription_started_on", "DATE NOT NULL DEFAULT CURRENT_DATE"),
        ("subscription_renews_on", "DATE NOT NULL DEFAULT CURRENT_DATE"),
        ("subscription_amount", "INTEGER"),
    )
    for name, definition in additions:
        if name not in columns:
            statements.append(f"ALTER TABLE tenants ADD COLUMN {name} {definition}")
            if "DEFAULT" in definition:
                statements.append(f"ALTER TABLE tenants ALTER COLUMN {name} DROP DEFAULT")
    if not statements:
        return
    with bind.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_user_token_version(bind) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "token_version" in columns:
        return
    with bind.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        )


def ensure_child_tenant_ids(bind) -> None:
    """Add tenant_id to child rows and copy it from the parent hospital record."""
    from sqlalchemy import inspect, text

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    backfills = (
        ("bill_items", "UPDATE bill_items AS child SET tenant_id = parent.tenant_id FROM opd_visits AS parent WHERE child.visit_id = parent.id AND child.tenant_id IS NULL"),
        ("payment_transactions", "UPDATE payment_transactions AS child SET tenant_id = parent.tenant_id FROM opd_visits AS parent WHERE child.visit_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_bills", "UPDATE ipd_bills AS child SET tenant_id = parent.tenant_id FROM ipd_admissions AS parent WHERE child.admission_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_bill_items", "UPDATE ipd_bill_items AS child SET tenant_id = parent.tenant_id FROM ipd_bills AS parent WHERE child.bill_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_payment_transactions", "UPDATE ipd_payment_transactions AS child SET tenant_id = parent.tenant_id FROM ipd_bills AS parent WHERE child.bill_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_admission_care_team", "UPDATE ipd_admission_care_team AS child SET tenant_id = parent.tenant_id FROM ipd_admissions AS parent WHERE child.admission_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_admission_billing", "UPDATE ipd_admission_billing AS child SET tenant_id = parent.tenant_id FROM ipd_admissions AS parent WHERE child.admission_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_insurance_claims", "UPDATE ipd_insurance_claims AS child SET tenant_id = parent.tenant_id FROM ipd_admissions AS parent WHERE child.admission_id = parent.id AND child.tenant_id IS NULL"),
        ("ipd_doctor_visits", "UPDATE ipd_doctor_visits AS child SET tenant_id = parent.tenant_id FROM ipd_admissions AS parent WHERE child.admission_id = parent.id AND child.tenant_id IS NULL"),
        ("dispensing_items", "UPDATE dispensing_items AS child SET tenant_id = parent.tenant_id FROM dispensings AS parent WHERE child.dispensing_id = parent.id AND child.tenant_id IS NULL"),
        ("lab_result_parameters", "UPDATE lab_result_parameters AS child SET tenant_id = parent.tenant_id FROM lab_results AS parent WHERE child.lab_result_id = parent.id AND child.tenant_id IS NULL"),
        ("shift_handover_patients", "UPDATE shift_handover_patients AS child SET tenant_id = parent.tenant_id FROM shift_handovers AS parent WHERE child.handover_id = parent.id AND child.tenant_id IS NULL"),
        ("nurse_workforce_rosters", "UPDATE nurse_workforce_rosters AS child SET tenant_id = parent.tenant_id FROM users AS parent WHERE child.nurse_id = parent.id AND child.tenant_id IS NULL"),
    )
    with bind.begin() as connection:
        for table, update_sql in backfills:
            if table not in tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "tenant_id" not in columns:
                connection.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)")
                )
                connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)"))
            connection.execute(text(update_sql))


class TenantScoped(Base):
    """Hospital-owned row. tenant_id is the hospital."""

    __abstract__ = True

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
