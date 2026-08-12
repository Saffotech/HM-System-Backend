"""Add medicine_name to dispensing_items (pharmacy dispense 500 fix).

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-08-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, Sequence[str], None] = "i2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dispensing_items" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("dispensing_items")}
    if "medicine_name" in columns:
        return
    op.add_column(
        "dispensing_items",
        sa.Column("medicine_name", sa.String(255), nullable=False, server_default=""),
    )
    op.alter_column("dispensing_items", "medicine_name", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dispensing_items" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("dispensing_items")}
    if "medicine_name" not in columns:
        return
    op.drop_column("dispensing_items", "medicine_name")
