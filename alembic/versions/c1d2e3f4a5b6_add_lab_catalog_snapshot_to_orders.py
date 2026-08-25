"""Add catalog linkage and price snapshots to lab orders.

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5b6
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector, table: str, column: str) -> bool:
    return table in inspector.get_table_names() and any(
        item["name"] == column for item in inspector.get_columns(table)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lab_test_orders" not in inspector.get_table_names():
        return

    if not _column_exists(inspector, "lab_test_orders", "lab_test_id"):
        op.add_column(
            "lab_test_orders",
            sa.Column("lab_test_id", sa.Integer(), nullable=True),
        )
    if not _column_exists(inspector, "lab_test_orders", "price"):
        op.add_column(
            "lab_test_orders",
            sa.Column("price", sa.Numeric(10, 2), nullable=True),
        )

    inspector = sa.inspect(bind)
    foreign_keys = {
        item["name"] for item in inspector.get_foreign_keys("lab_test_orders")
    }
    if "fk_lab_test_orders_lab_test_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_lab_test_orders_lab_test_id",
            "lab_test_orders",
            "lab_tests",
            ["lab_test_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    indexes = {item["name"] for item in inspector.get_indexes("lab_test_orders")}
    if "ix_lab_test_orders_lab_test_id" not in indexes:
        op.create_index(
            "ix_lab_test_orders_lab_test_id",
            "lab_test_orders",
            ["lab_test_id"],
        )

    # Backfill only exact name + department matches. Unmatched orders remain
    # nullable and are reported for review instead of receiving invented prices.
    bind.execute(
        sa.text(
            """
            UPDATE lab_test_orders AS orders
            SET lab_test_id = tests.id,
                price = tests.price
            FROM lab_tests AS tests
            WHERE orders.lab_test_id IS NULL
              AND lower(trim(orders.test_name)) = lower(trim(tests.test_name))
              AND orders.department_id = tests.department_id
            """
        )
    )
    unmatched = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM lab_test_orders
            WHERE lab_test_id IS NULL OR price IS NULL
            """
        )
    ).scalar_one()
    if unmatched:
        print(
            f"Lab order catalog backfill: {unmatched} orders remain unmatched "
            "(lab_test_id/price left NULL)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lab_test_orders" not in inspector.get_table_names():
        return

    indexes = {item["name"] for item in inspector.get_indexes("lab_test_orders")}
    if "ix_lab_test_orders_lab_test_id" in indexes:
        op.drop_index("ix_lab_test_orders_lab_test_id", table_name="lab_test_orders")

    foreign_keys = {
        item["name"] for item in inspector.get_foreign_keys("lab_test_orders")
    }
    if "fk_lab_test_orders_lab_test_id" in foreign_keys:
        op.drop_constraint(
            "fk_lab_test_orders_lab_test_id",
            "lab_test_orders",
            type_="foreignkey",
        )

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "lab_test_orders", "price"):
        op.drop_column("lab_test_orders", "price")
    if _column_exists(inspector, "lab_test_orders", "lab_test_id"):
        op.drop_column("lab_test_orders", "lab_test_id")
