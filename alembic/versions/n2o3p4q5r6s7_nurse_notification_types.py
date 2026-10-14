"""Add nurse notification types and reference types.

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "n2o3p4q5r6s7"
down_revision: Union[str, Sequence[str], None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'HANDOVER_TAKEN_OVER'"
    )
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SHIFT_UPDATED'"
    )
    op.execute(
        "ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'HANDOVER'"
    )
    op.execute(
        "ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'ALERT'"
    )


def downgrade() -> None:
    pass
