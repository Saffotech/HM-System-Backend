"""Persistent bed assignment: one active nurse per bed.

Revision ID: e8f9a0b1c2d3
Revises: n7o8p9q0r1s2
Create Date: 2026-07-27

Beds stay assigned until admin changes them (not daily/shift-scoped).
Adds assigned_until; replaces unique (bed, date, shift) with unique (bed) where active.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "n7o8p9q0r1s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "nurse_shift_bed_allocations" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("nurse_shift_bed_allocations")}
    if "assigned_until" not in columns:
        op.add_column(
            "nurse_shift_bed_allocations",
            sa.Column("assigned_until", sa.Date(), nullable=True),
        )

    # Keep newest active row per bed; deactivate older duplicates.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, bed_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY bed_id
                           ORDER BY created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM nurse_shift_bed_allocations
                WHERE is_active = true
            )
            UPDATE nurse_shift_bed_allocations AS a
            SET is_active = false,
                assigned_until = COALESCE(a.assigned_until, CURRENT_DATE),
                updated_at = NOW()
            FROM ranked
            WHERE a.id = ranked.id
              AND ranked.rn > 1
            """
        )
    )

    indexes = {idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")}
    if "uq_active_bed_shift_allocation" in indexes:
        op.drop_index(
            "uq_active_bed_shift_allocation",
            table_name="nurse_shift_bed_allocations",
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")}
    if "uq_active_bed_allocation" not in indexes:
        op.create_index(
            "uq_active_bed_allocation",
            "nurse_shift_bed_allocations",
            ["bed_id"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nurse_shift_bed_allocations" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")}
    if "uq_active_bed_allocation" in indexes:
        op.drop_index(
            "uq_active_bed_allocation",
            table_name="nurse_shift_bed_allocations",
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")}
    if "uq_active_bed_shift_allocation" not in indexes:
        op.create_index(
            "uq_active_bed_shift_allocation",
            "nurse_shift_bed_allocations",
            ["bed_id", "shift_date", "shift_name"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

    columns = {c["name"] for c in inspector.get_columns("nurse_shift_bed_allocations")}
    if "assigned_until" in columns:
        op.drop_column("nurse_shift_bed_allocations", "assigned_until")
