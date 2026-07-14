"""Add no_show to appointmentstatus enum

Revision ID: e3f4a5b6c7d8
Revises: a7b8c9d0e1f2, d2e3f4a5b6c7
Create Date: 2026-07-13 14:45:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = ("a7b8c9d0e1f2", "d2e3f4a5b6c7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE appointmentstatus ADD VALUE 'no_show';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL cannot easily remove an enum value; leave no_show in place.
    pass
