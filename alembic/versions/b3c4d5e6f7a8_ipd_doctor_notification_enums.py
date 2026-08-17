"""Add IPD admit notification enums.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'IPD_ADMITTED'")
    op.execute("ALTER TYPE sourcemodule ADD VALUE IF NOT EXISTS 'IPD'")
    op.execute("ALTER TYPE referencetype ADD VALUE IF NOT EXISTS 'ADMISSION'")


def downgrade() -> None:
    pass
