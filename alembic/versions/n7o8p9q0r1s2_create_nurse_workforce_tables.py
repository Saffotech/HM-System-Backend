"""Create nurse workforce shift and roster tables.

Revision ID: n7o8p9q0r1s2
Revises: d3e4f5a6b7c8
Create Date: 2026-07-24

Uses a unique revision id (previous e4f5a6b7c8d9 collided with
appointment_status_no_show). Only creates shifts + rosters; drops
leave/attendance tables if they already exist from earlier drafts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "nurse_workforce_attendance" in tables:
        op.drop_table("nurse_workforce_attendance")
        tables.discard("nurse_workforce_attendance")
    if "nurse_workforce_leaves" in tables:
        op.drop_table("nurse_workforce_leaves")
        tables.discard("nurse_workforce_leaves")

    if "nurse_workforce_shifts" not in tables:
        op.create_table(
            "nurse_workforce_shifts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=True),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("color", sa.String(length=20), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("weekly_mask", sa.String(length=20), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_nws_id", "nurse_workforce_shifts", ["id"])
        op.create_index("ix_nws_name", "nurse_workforce_shifts", ["name"])
        op.create_index("ix_nws_is_active", "nurse_workforce_shifts", ["is_active"])

    if "nurse_workforce_rosters" not in tables:
        op.create_table(
            "nurse_workforce_rosters",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nurse_id", sa.Integer(), nullable=False),
            sa.Column("shift_id", sa.Integer(), nullable=False),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("roster_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="scheduled"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("assigned_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["nurse_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["shift_id"], ["nurse_workforce_shifts.id"]),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
            sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "nurse_id", "roster_date", "shift_id", name="uq_nurse_roster_date_shift"
            ),
        )
        op.create_index("ix_nwr_id", "nurse_workforce_rosters", ["id"])
        op.create_index("ix_nwr_nurse_id", "nurse_workforce_rosters", ["nurse_id"])
        op.create_index("ix_nwr_shift_id", "nurse_workforce_rosters", ["shift_id"])
        op.create_index("ix_nwr_department_id", "nurse_workforce_rosters", ["department_id"])
        op.create_index("ix_nwr_roster_date", "nurse_workforce_rosters", ["roster_date"])
        op.create_index("ix_nwr_status", "nurse_workforce_rosters", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table in ("nurse_workforce_rosters", "nurse_workforce_shifts"):
        if table in tables:
            op.drop_table(table)
