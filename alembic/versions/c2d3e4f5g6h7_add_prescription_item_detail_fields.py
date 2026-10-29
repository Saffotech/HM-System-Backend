"""Add optional medicine detail fields on prescription_items.

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2026-08-26

Existing doctor payloads (medicine_name, dosage, frequency, duration,
instructions) stay valid. New columns are nullable so old rows and old
clients do not break.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5g6h7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "prescription_items"):
        return

    columns = (
        ("form", sa.String(length=50)),
        ("dose", sa.String(length=50)),
        ("route", sa.String(length=50)),
        ("timing", sa.String(length=50)),
        ("quantity", sa.Integer()),
        ("quantity_unit", sa.String(length=50)),
    )
    for name, col_type in columns:
        if not _column_exists(inspector, "prescription_items", name):
            op.add_column(
                "prescription_items",
                sa.Column(name, col_type, nullable=True),
            )
            inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "prescription_items"):
        return

    for name in (
        "quantity_unit",
        "quantity",
        "timing",
        "route",
        "dose",
        "form",
    ):
        if _column_exists(inspector, "prescription_items", name):
            op.drop_column("prescription_items", name)
            inspector = sa.inspect(bind)
