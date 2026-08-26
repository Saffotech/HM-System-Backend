"""Add notifications for nurse-recorded doctor visits.

Revision ID: a1b2c3d4e5f7
Revises: laborder20260825, z9a0b1c2d3e4
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = (
    "laborder20260825",
    "z9a0b1c2d3e4",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notificationtype "
        "ADD VALUE IF NOT EXISTS 'NURSE_DOCTOR_VISIT_CREATED'"
    )
    op.execute(
        "ALTER TYPE notificationtype "
        "ADD VALUE IF NOT EXISTS 'NURSE_DOCTOR_VISIT_UPDATED'"
    )
def downgrade() -> None:
    # PostgreSQL cannot remove enum values without rebuilding the enum type.
    pass
