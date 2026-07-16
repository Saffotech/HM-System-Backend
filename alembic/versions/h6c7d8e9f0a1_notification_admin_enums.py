"""add ADMIN_UPDATE notification type and USER/SCHEDULE/LEAVE reference types

Revision ID: h6c7d8e9f0a1
Revises: g5b6c7d8e9f0
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "h6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "g5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ADMIN_UPDATE'")
    op.execute("ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'USER'")
    op.execute("ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'SCHEDULE'")
    op.execute("ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'LEAVE'")


def downgrade() -> None:
    pass
