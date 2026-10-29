"""Create patient_other_visits table.

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-08-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_other_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("person_name", sa.String(length=255), nullable=False),
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
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["voided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_patient_other_visits_id"),
        "patient_other_visits",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_other_visits_patient_id"),
        "patient_other_visits",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_other_visits_department_id"),
        "patient_other_visits",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_other_visits_visited_at"),
        "patient_other_visits",
        ["visited_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_other_visits_recorded_by"),
        "patient_other_visits",
        ["recorded_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_other_visits_is_voided"),
        "patient_other_visits",
        ["is_voided"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_other_visits_is_voided"), table_name="patient_other_visits")
    op.drop_index(op.f("ix_patient_other_visits_recorded_by"), table_name="patient_other_visits")
    op.drop_index(op.f("ix_patient_other_visits_visited_at"), table_name="patient_other_visits")
    op.drop_index(op.f("ix_patient_other_visits_department_id"), table_name="patient_other_visits")
    op.drop_index(op.f("ix_patient_other_visits_patient_id"), table_name="patient_other_visits")
    op.drop_index(op.f("ix_patient_other_visits_id"), table_name="patient_other_visits")
    op.drop_table("patient_other_visits")
