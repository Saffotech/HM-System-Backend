"""Ensure appointmentstatus includes no_show.

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-07-17

Doctor dashboard calls mark_past_scheduled_as_no_show on every
GET /appointments/today. Without no_show on the PG enum that update
raises and the whole today list fails (booked patients never appear).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, Sequence[str], None] = "t9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE cannot run inside a transaction block on older PG; Alembic
    # PostgresqlImpl usually commits around this. Use DO-block for safety.
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
    pass
