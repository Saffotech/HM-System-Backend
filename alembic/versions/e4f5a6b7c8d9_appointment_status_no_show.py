"""Add no_show to appointmentstatus enum

Revision ID: e4f5a6b7c8d9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-13 14:45:00.000000

Was previously a duplicate of revision e3f4a5b6c7d8 (doctor_profiles).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE appointmentstatus ADD VALUE 'no_show';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
            WHEN undefined_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL cannot easily remove an enum value; leave no_show in place.
    pass
