"""Store the time an appointment was cancelled.

Revision ID: e7f8a9b0c1d2
Revises: c2d3e4f5g6h7, ddf60eb3834f, laborder20260825, n4o5p6q7r8s9, o8p9q0r1s2t3
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = (
    "c2d3e4f5g6h7",
    "ddf60eb3834f",
    "laborder20260825",
    "n4o5p6q7r8s9",
    "o8p9q0r1s2t3",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "appointments" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("appointments")}
    if "cancelled_at" in columns:
        return
    op.add_column(
        "appointments",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "appointments" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("appointments")}
    if "cancelled_at" not in columns:
        return
    op.drop_column("appointments", "cancelled_at")
