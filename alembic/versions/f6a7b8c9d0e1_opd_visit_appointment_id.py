"""opd_visits appointment_id link for payment-gated queue

Revision ID: f6a7b8c9d0e1
Revises: b8e885b35927
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "b8e885b35927"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "opd_visits",
        sa.Column("appointment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_opd_visits_appointment_id",
        "opd_visits",
        "appointments",
        ["appointment_id"],
        ["id"],
    )
    op.create_index(
        "ix_opd_visits_appointment_id",
        "opd_visits",
        ["appointment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_opd_visits_appointment_id", table_name="opd_visits")
    op.drop_constraint("fk_opd_visits_appointment_id", "opd_visits", type_="foreignkey")
    op.drop_column("opd_visits", "appointment_id")
