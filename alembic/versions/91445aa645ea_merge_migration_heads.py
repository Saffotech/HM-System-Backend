"""merge migration heads

Revision ID: 91445aa645ea
Revises: f1a2b3c4d5e6, j3k4l5m6n7o8
Create Date: 2026-08-24 10:01:52.729272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91445aa645ea"
down_revision: Union[str, Sequence[str], None] = ("f1a2b3c4d5e6", "j3k4l5m6n7o8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
