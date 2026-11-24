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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("patient_queue")}
    if "called_at" not in columns:
        op.add_column(
            "patient_queue",
            sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'queuestatus')
               AND NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'queuestatus' AND e.enumlabel = 'no_show'
               ) THEN
                ALTER TYPE queuestatus ADD VALUE 'no_show';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column("patient_queue", "called_at")