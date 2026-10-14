"""add dispensing_items for item-level pharmacy dispense

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispensing_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dispensing_id", sa.Integer(), nullable=False),
        sa.Column("prescription_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity_dispensed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["dispensing_id"], ["dispensings.id"]),
        sa.ForeignKeyConstraint(["prescription_item_id"], ["prescription_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dispensing_items_dispensing_id", "dispensing_items", ["dispensing_id"])
    op.create_index(
        "ix_dispensing_items_prescription_item_id",
        "dispensing_items",
        ["prescription_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dispensing_items_prescription_item_id", table_name="dispensing_items")
    op.drop_index("ix_dispensing_items_dispensing_id", table_name="dispensing_items")
    op.drop_table("dispensing_items")
