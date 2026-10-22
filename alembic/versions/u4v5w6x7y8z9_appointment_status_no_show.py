"""Add no_show to the appointmentstatus enum.

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8, e7f8a9b0c1d2
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "u4v5w6x7y8z9"
down_revision: Union[str, Sequence[str], None] = ("t3u4v5w6x7y8", "e7f8a9b0c1d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE appointmentstatus ADD VALUE IF NOT EXISTS 'no_show'")


def downgrade() -> None:
    pass
