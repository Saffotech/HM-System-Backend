"""Normalize patient_queue priority casing (NORMAL → normal).

Revision ID: t9u0v1w2x3y4
Revises: s8t9u0v1w2x3
Create Date: 2026-07-17

Doctor dashboard GET /appointments/today crashed while loading queue rows
whose priority was stored as uppercase enum names (NORMAL) while the app
expects lowercase values (normal).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t9u0v1w2x3y4"
down_revision: Union[str, Sequence[str], None] = "s8t9u0v1w2x3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "patient_queue" not in inspector.get_table_names():
        return

    cols = {c["name"]: c for c in inspector.get_columns("patient_queue")}
    if "priority" not in cols:
        return

    op.execute(
        sa.text(
            "UPDATE patient_queue SET priority = lower(priority) "
            "WHERE priority IS NOT NULL AND priority <> lower(priority)"
        )
    )


def downgrade() -> None:
    # Irreversible data normalization; no-op.
    pass
