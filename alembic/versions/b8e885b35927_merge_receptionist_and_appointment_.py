"""merge receptionist and appointment branches

Revision ID: b8e885b35927
Revises: a9b0c1d2e3f4, e5f6a7b8c9d0
Create Date: 2026-06-30 11:41:10.008432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8e885b35927"
down_revision: Union[str, Sequence[str], None] = ("a9b0c1d2e3f4", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
