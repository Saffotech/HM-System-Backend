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


def _index_names(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dispensing_items" not in inspector.get_table_names():
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
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "dispensing_items")
    if "ix_dispensing_items_dispensing_id" not in indexes:
        op.create_index("ix_dispensing_items_dispensing_id", "dispensing_items", ["dispensing_id"])
    if "ix_dispensing_items_prescription_item_id" not in indexes:
        op.create_index(
            "ix_dispensing_items_prescription_item_id",
            "dispensing_items",
            ["prescription_item_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dispensing_items" not in inspector.get_table_names():
        return
    indexes = _index_names(inspector, "dispensing_items")
    if "ix_dispensing_items_prescription_item_id" in indexes:
        op.drop_index("ix_dispensing_items_prescription_item_id", table_name="dispensing_items")
    if "ix_dispensing_items_dispensing_id" in indexes:
        op.drop_index("ix_dispensing_items_dispensing_id", table_name="dispensing_items")
    op.drop_table("dispensing_items")
