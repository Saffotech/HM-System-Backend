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
    )
    for name, definition in additions:
        if name not in columns:
            statements.append(f"ALTER TABLE tenants ADD COLUMN {name} {definition}")
            statements.append(f"ALTER TABLE tenants ALTER COLUMN {name} DROP DEFAULT")
    if not statements:
        return
    with bind.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


class TenantScoped(Base):
    """Hospital-owned row. tenant_id is the hospital."""

    __abstract__ = True

    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
