"""Create nurse_doctor_visits table.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nurse_doctor_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("doctor_name", sa.String(length=255), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.Column("recorded_by_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_by_name", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_voided",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("voided_by", sa.Integer(), nullable=True),
        sa.Column("voided_by_name", sa.String(length=255), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["voided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_id"),
        "nurse_doctor_visits",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_patient_id"),
        "nurse_doctor_visits",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_doctor_id"),
        "nurse_doctor_visits",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_visited_at"),
        "nurse_doctor_visits",
        ["visited_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_recorded_by"),
        "nurse_doctor_visits",
        ["recorded_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nurse_doctor_visits_is_voided"),
        "nurse_doctor_visits",
        ["is_voided"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_nurse_doctor_visits_is_voided"), table_name="nurse_doctor_visits")
    op.drop_index(op.f("ix_nurse_doctor_visits_recorded_by"), table_name="nurse_doctor_visits")
    op.drop_index(op.f("ix_nurse_doctor_visits_visited_at"), table_name="nurse_doctor_visits")
    op.drop_index(op.f("ix_nurse_doctor_visits_doctor_id"), table_name="nurse_doctor_visits")
    op.drop_index(op.f("ix_nurse_doctor_visits_patient_id"), table_name="nurse_doctor_visits")
    op.drop_index(op.f("ix_nurse_doctor_visits_id"), table_name="nurse_doctor_visits")
    op.drop_table("nurse_doctor_visits")
