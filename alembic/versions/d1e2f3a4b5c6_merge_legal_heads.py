"""Merge legal snapshot and legal finance profile heads.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4, b8d2f0c3e5a7
"""
from typing import Sequence, Union

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = ("c9d0e1f2a3b4", "b8d2f0c3e5a7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
