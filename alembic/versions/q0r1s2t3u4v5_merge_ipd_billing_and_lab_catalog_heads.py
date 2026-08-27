"""Merge IPD billing head with lab catalog / prescription detail head.

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4, c2d3e4f5g6h7
Create Date: 2026-08-27
"""
from typing import Sequence, Union

revision: str = "q0r1s2t3u4v5"
down_revision: Union[str, Sequence[str], None] = ("p9q0r1s2t3u4", "c2d3e4f5g6h7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
