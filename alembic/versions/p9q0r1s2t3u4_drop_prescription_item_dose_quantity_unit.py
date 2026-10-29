"""Drop unused dose and quantity_unit from prescription_items.

Revision ID: p9q0r1s2t3u4
Revises: c2d3e4f5g6h7, o8p9q0r1s2t3, n4o5p6q7r8s9
Create Date: 2026-08-27

Merges remaining heads and drops dose / quantity_unit.
dosage (strength) is kept. Frontend may still send dose / quantity_unit;
API schemas ignore those keys.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p9q0r1s2t3u4"
down_revision: Union[str, Sequence[str], None] = (
    "c2d3e4f5g6h7",
    "o8p9q0r1s2t3",
    "n4o5p6q7r8s9",
)
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

    for name in ("dose", "quantity_unit"):
        if _column_exists(inspector, "prescription_items", name):
            op.drop_column("prescription_items", name)
            inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "prescription_items"):
        return

    if not _column_exists(inspector, "prescription_items", "dose"):
        op.add_column(
            "prescription_items",
            sa.Column("dose", sa.String(length=50), nullable=True),
        )
        inspector = sa.inspect(bind)

    if not _column_exists(inspector, "prescription_items", "quantity_unit"):
        op.add_column(
            "prescription_items",
            sa.Column("quantity_unit", sa.String(length=50), nullable=True),
        )
