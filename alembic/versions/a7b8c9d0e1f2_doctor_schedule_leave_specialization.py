"""doctor schedules, leaves, user specialization

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("specialization", sa.String(length=120), nullable=True))

    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("shift_start", sa.Time(), nullable=False),
        sa.Column("shift_end", sa.Time(), nullable=False),
        sa.Column("consultation_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])
    op.create_index("ix_doctor_schedules_day_of_week", "doctor_schedules", ["day_of_week"])

    op.create_table(
        "doctor_leaves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("leave_type", sa.Enum("leave", "holiday", name="doctorleavetype"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctor_leaves_doctor_id", "doctor_leaves", ["doctor_id"])
    op.create_index("ix_doctor_leaves_start_date", "doctor_leaves", ["start_date"])
    op.create_index("ix_doctor_leaves_end_date", "doctor_leaves", ["end_date"])


def downgrade() -> None:
    op.drop_index("ix_doctor_leaves_end_date", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_start_date", table_name="doctor_leaves")
    op.drop_index("ix_doctor_leaves_doctor_id", table_name="doctor_leaves")
    op.drop_table("doctor_leaves")
    op.execute("DROP TYPE IF EXISTS doctorleavetype")

    op.drop_index("ix_doctor_schedules_day_of_week", table_name="doctor_schedules")
    op.drop_index("ix_doctor_schedules_doctor_id", table_name="doctor_schedules")
    op.drop_table("doctor_schedules")

    op.drop_column("users", "specialization")
