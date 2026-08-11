"""Indexes for OPD billing dashboard counts and today filters.

Revision ID: g0a1b2c3d4e5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    visit_indexes = _index_names(inspector, "opd_visits")
    if "ix_opd_visits_visit_date" not in visit_indexes:
        op.create_index("ix_opd_visits_visit_date", "opd_visits", ["visit_date"])
    if "ix_opd_visits_payment_status" not in visit_indexes:
        op.create_index("ix_opd_visits_payment_status", "opd_visits", ["payment_status"])

    apt_indexes = _index_names(inspector, "appointments")
    if "ix_appointments_scheduled_at" not in apt_indexes:
        op.create_index("ix_appointments_scheduled_at", "appointments", ["scheduled_at"])
    if "ix_appointments_scheduled_at_status" not in apt_indexes:
        op.create_index(
            "ix_appointments_scheduled_at_status",
            "appointments",
            ["scheduled_at", "status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    apt_indexes = _index_names(inspector, "appointments")
    if "ix_appointments_scheduled_at_status" in apt_indexes:
        op.drop_index("ix_appointments_scheduled_at_status", table_name="appointments")
    if "ix_appointments_scheduled_at" in apt_indexes:
        op.drop_index("ix_appointments_scheduled_at", table_name="appointments")

    visit_indexes = _index_names(inspector, "opd_visits")
    if "ix_opd_visits_payment_status" in visit_indexes:
        op.drop_index("ix_opd_visits_payment_status", table_name="opd_visits")
    if "ix_opd_visits_visit_date" in visit_indexes:
        op.drop_index("ix_opd_visits_visit_date", table_name="opd_visits")
