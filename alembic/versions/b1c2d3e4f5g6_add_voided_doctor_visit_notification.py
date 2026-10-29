"""Add voided nurse doctor-visit notification type.

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f7
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f5g6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notificationtype "
        "ADD VALUE IF NOT EXISTS 'NURSE_DOCTOR_VISIT_VOIDED'"
    )


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without rebuilding the enum type.
    pass
