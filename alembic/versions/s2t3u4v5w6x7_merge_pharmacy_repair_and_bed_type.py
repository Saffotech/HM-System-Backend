"""Merge pharmacy pricing repair and bed_type heads.

Revision ID: s2t3u4v5w6x7
Revises: q0r1s2t3u4v5, r1s2t3u4v5w6
Create Date: 2026-09-04

q0r1s2t3u4v5 was assigned twice after a branch merge (pharmacy column
repair and bed_type). The bed_type revision is now r1s2t3u4v5w6; this
merge restores a single Alembic head.
"""
from typing import Sequence, Union

revision: str = "s2t3u4v5w6x7"
down_revision: Union[str, Sequence[str], None] = ("q0r1s2t3u4v5", "r1s2t3u4v5w6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
