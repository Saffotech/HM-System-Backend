"""Create nurse_shift_bed_allocation_history + composite index (Phase 6).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "nurse_shift_bed_allocation_history" not in tables:
        op.create_table(
            "nurse_shift_bed_allocation_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("allocation_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("old_nurse_id", sa.Integer(), nullable=True),
            sa.Column("new_nurse_id", sa.Integer(), nullable=True),
            sa.Column("old_bed_id", sa.Integer(), nullable=True),
            sa.Column("new_bed_id", sa.Integer(), nullable=True),
            sa.Column("shift_date", sa.Date(), nullable=True),
            sa.Column("shift_name", sa.String(length=100), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["allocation_id"],
                ["nurse_shift_bed_allocations.id"],
            ),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["old_nurse_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["new_nurse_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["old_bed_id"], ["beds.id"]),
            sa.ForeignKeyConstraint(["new_bed_id"], ["beds.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_nsbah_id",
            "nurse_shift_bed_allocation_history",
            ["id"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_allocation_id",
            "nurse_shift_bed_allocation_history",
            ["allocation_id"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_action",
            "nurse_shift_bed_allocation_history",
            ["action"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_actor_id",
            "nurse_shift_bed_allocation_history",
            ["actor_id"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_shift_date",
            "nurse_shift_bed_allocation_history",
            ["shift_date"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_shift_name",
            "nurse_shift_bed_allocation_history",
            ["shift_name"],
            unique=False,
        )
        op.create_index(
            "ix_nsbah_created_at",
            "nurse_shift_bed_allocation_history",
            ["created_at"],
            unique=False,
        )

    # Composite index for common list/report filters (additive, safe)
    if "nurse_shift_bed_allocations" in tables:
        indexes = {
            idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")
        }
        if "ix_nsba_date_shift_active" not in indexes:
            op.create_index(
                "ix_nsba_date_shift_active",
                "nurse_shift_bed_allocations",
                ["shift_date", "shift_name", "is_active"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "nurse_shift_bed_allocations" in tables:
        indexes = {
            idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")
        }
        if "ix_nsba_date_shift_active" in indexes:
            op.drop_index(
                "ix_nsba_date_shift_active",
                table_name="nurse_shift_bed_allocations",
            )

    if "nurse_shift_bed_allocation_history" not in tables:
        return

    for name in (
        "ix_nsbah_created_at",
        "ix_nsbah_shift_name",
        "ix_nsbah_shift_date",
        "ix_nsbah_actor_id",
        "ix_nsbah_action",
        "ix_nsbah_allocation_id",
        "ix_nsbah_id",
    ):
        indexes = {
            idx["name"]
            for idx in inspector.get_indexes("nurse_shift_bed_allocation_history")
        }
        if name in indexes:
            op.drop_index(name, table_name="nurse_shift_bed_allocation_history")

    op.drop_table("nurse_shift_bed_allocation_history")
