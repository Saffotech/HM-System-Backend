"""Add the current subscription onto tenants.

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t3u4v5w6x7y8"
down_revision: Union[str, Sequence[str], None] = "s2t3u4v5w6x7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tenants" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("tenants")}
    additions = (
        ("plan", sa.String(length=50), "Professional"),
        ("billing_cycle", sa.String(length=20), "Monthly"),
        ("trial_period", sa.String(length=20), "None"),
        ("tenant_status", sa.String(length=20), "Active"),
        ("subscription_status", sa.String(length=20), "Active"),
    )
    for name, type_, default in additions:
        if name not in columns:
            op.add_column("tenants", sa.Column(name, type_, nullable=False, server_default=default))
            op.alter_column("tenants", name, server_default=None)
    if "subscription_started_on" not in columns:
        op.add_column(
            "tenants",
            sa.Column("subscription_started_on", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        )
        op.alter_column("tenants", "subscription_started_on", server_default=None)
    if "subscription_renews_on" not in columns:
        op.add_column(
            "tenants",
            sa.Column("subscription_renews_on", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        )
        op.alter_column("tenants", "subscription_renews_on", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tenants" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("tenants")}
    for name in (
        "subscription_renews_on",
        "subscription_started_on",
        "subscription_status",
        "tenant_status",
        "trial_period",
        "billing_cycle",
        "plan",
    ):
        if name in columns:
            op.drop_column("tenants", name)
