"""Add pharmacy dispense pricing columns (amount / unit_price).

Revision ID: k4l5m6n7o8p9
Revises: 91445aa645ea
Create Date: 2026-08-24

Pharmacist enters line total (amount) at dispense time; unit_price is derived.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, Sequence[str], None] = "91445aa645ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dispensing_items" in inspector.get_table_names():
        cols = _columns(inspector, "dispensing_items")
        if "unit_price" not in cols:
            op.add_column(
                "dispensing_items",
                sa.Column(
                    "unit_price",
                    sa.Numeric(12, 2),
                    nullable=False,
                    server_default="0",
                ),
            )
            op.alter_column("dispensing_items", "unit_price", server_default=None)
        if "amount" not in cols:
            op.add_column(
                "dispensing_items",
                sa.Column(
                    "amount",
                    sa.Numeric(12, 2),
                    nullable=False,
                    server_default="0",
                ),
            )
            op.alter_column("dispensing_items", "amount", server_default=None)

    if "dispensings" in inspector.get_table_names():
        cols = _columns(inspector, "dispensings")
        if "total_amount" not in cols:
            op.add_column(
                "dispensings",
                sa.Column(
                    "total_amount",
                    sa.Numeric(12, 2),
                    nullable=False,
                    server_default="0",
                ),
            )
            op.alter_column("dispensings", "total_amount", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dispensings" in inspector.get_table_names():
        cols = _columns(inspector, "dispensings")
        if "total_amount" in cols:
            op.drop_column("dispensings", "total_amount")

    if "dispensing_items" in inspector.get_table_names():
        cols = _columns(inspector, "dispensing_items")
        if "amount" in cols:
            op.drop_column("dispensing_items", "amount")
        if "unit_price" in cols:
            op.drop_column("dispensing_items", "unit_price")
