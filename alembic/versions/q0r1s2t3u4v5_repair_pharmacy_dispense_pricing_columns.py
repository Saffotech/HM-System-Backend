"""Repair missing pharmacy dispense pricing columns.

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4
Create Date: 2026-08-28

k4l5m6n7o8p9 was already marked applied, but this database never received
dispensing_items.unit_price / amount or dispensings.total_amount. Re-apply
those columns idempotently so pharmacy history and IPD bill preview work.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q0r1s2t3u4v5"
down_revision: Union[str, Sequence[str], None] = "p9q0r1s2t3u4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _add_numeric(table: str, column: str) -> None:
    op.add_column(
        table,
        sa.Column(
            column,
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column(table, column, server_default=None)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dispensing_items" in inspector.get_table_names():
        cols = _columns(inspector, "dispensing_items")
        if "unit_price" not in cols:
            _add_numeric("dispensing_items", "unit_price")
        if "amount" not in cols:
            _add_numeric("dispensing_items", "amount")

    inspector = sa.inspect(bind)
    if "dispensings" in inspector.get_table_names():
        cols = _columns(inspector, "dispensings")
        if "total_amount" not in cols:
            _add_numeric("dispensings", "total_amount")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dispensings" in inspector.get_table_names():
        cols = _columns(inspector, "dispensings")
        if "total_amount" in cols:
            op.drop_column("dispensings", "total_amount")

    inspector = sa.inspect(bind)
    if "dispensing_items" in inspector.get_table_names():
        cols = _columns(inspector, "dispensing_items")
        if "amount" in cols:
            op.drop_column("dispensing_items", "amount")
        if "unit_price" in cols:
            op.drop_column("dispensing_items", "unit_price")
