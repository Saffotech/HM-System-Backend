"""Add user_agent to audit_logs.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    if "user_agent" not in columns:
        op.add_column(
            "audit_logs",
            sa.Column("user_agent", sa.String(length=512), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    if "user_agent" in columns:
        op.drop_column("audit_logs", "user_agent")
