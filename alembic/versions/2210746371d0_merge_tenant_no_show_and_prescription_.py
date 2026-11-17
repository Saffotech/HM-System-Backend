"""merge tenant, no_show, and prescription heads

Revision ID: 2210746371d0
Revises: f8a9b0c1d2e3, p9q0r1s2t3u4, u4v5w6x7y8z9
Create Date: 2026-11-02 17:15:56.030154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2210746371d0'
down_revision: Union[str, Sequence[str], None] = ('f8a9b0c1d2e3', 'p9q0r1s2t3u4', 'u4v5w6x7y8z9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
