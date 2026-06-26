"""add called_at and no_show

Revision ID: 7954ceb7aea4
Revises: d4e5f6a7b8c9
Create Date: 2026-06-23 16:43:16.058113
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7954ceb7aea4"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "patient_queue",
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE queuestatus ADD VALUE 'no_show';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column("patient_queue", "called_at")