"""Merge queue branch and status-simplify branch heads.

Revision ID: r7s8t9u0v1w2
Revises: c0d1e2f3a4b5, q5r6s7t8u9v0
Create Date: 2026-07-16

"""
from typing import Sequence, Union

revision: str = "r7s8t9u0v1w2"
down_revision: Union[str, Sequence[str], None] = ("c0d1e2f3a4b5", "q5r6s7t8u9v0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
