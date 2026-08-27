"""Merge hospital live baseline with IPD billing / insurance heads.

Revision ID: p9q0r1s2t3u4
Revises: c9d0e1f2a3b4, o8p9q0r1s2t3
Create Date: 2026-08-27

After pull: one branch stamped the Hospital live baseline (c9d0…), another
added pharmacy pricing → IPD visits → insurance/payment_type → admission
billing (…o8p9). This merge restores a single head.
"""
from typing import Sequence, Union

revision: str = "p9q0r1s2t3u4"
down_revision: Union[str, Sequence[str], None] = ("c9d0e1f2a3b4", "o8p9q0r1s2t3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
