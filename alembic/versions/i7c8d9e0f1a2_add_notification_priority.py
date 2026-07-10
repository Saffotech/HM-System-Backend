"""add notification priority column

Revision ID: i7c8d9e0f1a2
Revises: h6c7d8e9f0a1
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "h6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

priority_enum = sa.Enum("NORMAL", "HIGH", "CRITICAL", name="notificationpriority")


def upgrade() -> None:
    bind = op.get_bind()
    priority_enum.create(bind, checkfirst=True)

    op.add_column(
        "notifications",
        sa.Column(
            "priority",
            priority_enum,
            nullable=False,
            server_default="NORMAL",
        ),
    )
    op.create_index(
        op.f("ix_notifications_priority"),
        "notifications",
        ["priority"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_priority"), table_name="notifications")
    op.drop_column("notifications", "priority")
    priority_enum.drop(op.get_bind(), checkfirst=True)
