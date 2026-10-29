"""Remap hidden appointment no_show rows to cancelled for OPD history.

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-07-17

Past unconsulted appointments were stored as no_show and excluded from the
OPD appointments list. Product rule is: after the day ends, unconsulted
appointments are cancelled (visible under Cancelled / All).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, Sequence[str], None] = "u0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "appointments" in tables:
        op.execute(
            sa.text(
                "UPDATE appointments SET status = 'cancelled' "
                "WHERE status::text = 'no_show'"
            )
        )

    if "patient_queue" in tables:
        # Queue column may be varchar or enum; compare via text.
        op.execute(
            sa.text(
                "UPDATE patient_queue SET status = 'cancelled' "
                "WHERE lower(status::text) = 'no_show'"
            )
        )


def downgrade() -> None:
    # Irreversible data remap — cannot distinguish auto-cancelled from user cancel.
    pass
