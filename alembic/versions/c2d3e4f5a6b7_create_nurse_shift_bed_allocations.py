"""Create nurse_shift_bed_allocations table.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "nurse_shift_bed_allocations" not in inspector.get_table_names():
        op.create_table(
            "nurse_shift_bed_allocations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nurse_id", sa.Integer(), nullable=False),
            sa.Column("bed_id", sa.Integer(), nullable=False),
            sa.Column("shift_date", sa.Date(), nullable=False),
            sa.Column("shift_name", sa.String(length=100), nullable=False),
            sa.Column("shift_start", sa.Time(), nullable=True),
            sa.Column("shift_end", sa.Time(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("assigned_by", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["nurse_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["bed_id"], ["beds.id"]),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
            sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_id"),
            "nurse_shift_bed_allocations",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_nurse_id"),
            "nurse_shift_bed_allocations",
            ["nurse_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_bed_id"),
            "nurse_shift_bed_allocations",
            ["bed_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_shift_date"),
            "nurse_shift_bed_allocations",
            ["shift_date"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_shift_name"),
            "nurse_shift_bed_allocations",
            ["shift_name"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_department_id"),
            "nurse_shift_bed_allocations",
            ["department_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_is_active"),
            "nurse_shift_bed_allocations",
            ["is_active"],
            unique=False,
        )
        op.create_index(
            op.f("ix_nurse_shift_bed_allocations_created_at"),
            "nurse_shift_bed_allocations",
            ["created_at"],
            unique=False,
        )
        # One active responsibility per bed per shift/date
        op.create_index(
            "uq_active_bed_shift_allocation",
            "nurse_shift_bed_allocations",
            ["bed_id", "shift_date", "shift_name"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "nurse_shift_bed_allocations" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("nurse_shift_bed_allocations")}
    if "uq_active_bed_shift_allocation" in indexes:
        op.drop_index(
            "uq_active_bed_shift_allocation",
            table_name="nurse_shift_bed_allocations",
        )

    for name in (
        "ix_nurse_shift_bed_allocations_created_at",
        "ix_nurse_shift_bed_allocations_is_active",
        "ix_nurse_shift_bed_allocations_department_id",
        "ix_nurse_shift_bed_allocations_shift_name",
        "ix_nurse_shift_bed_allocations_shift_date",
        "ix_nurse_shift_bed_allocations_bed_id",
        "ix_nurse_shift_bed_allocations_nurse_id",
        "ix_nurse_shift_bed_allocations_id",
    ):
        if name in indexes:
            op.drop_index(op.f(name), table_name="nurse_shift_bed_allocations")

    op.drop_table("nurse_shift_bed_allocations")
