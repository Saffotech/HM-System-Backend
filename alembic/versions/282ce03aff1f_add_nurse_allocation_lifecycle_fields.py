"""Add nurse bed allocation lifecycle fields safely.

Revision ID: 282ce03aff1f
Revises: d7e8f9a0b1c2

This migration intentionally changes only the two nurse bed allocation
lifecycle tables. It does not drop or recreate any existing tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "282ce03aff1f"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status as nullable first so existing rows can be backfilled safely.
    op.add_column(
        "nurse_shift_bed_allocations",
        sa.Column("status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "nurse_shift_bed_allocations",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill current lifecycle state. For old inactive rows, use the latest
    # terminal history event where available. Older auto-expiry events were
    # recorded as action='deactivated' with remarks beginning 'Auto-expired:'.
    op.execute(
        sa.text(
            """
            WITH latest_status_event AS (
                SELECT DISTINCT ON (allocation_id)
                    allocation_id,
                    action,
                    remarks
                FROM nurse_shift_bed_allocation_history
                WHERE allocation_id IS NOT NULL
                  AND action IN ('activated', 'deactivated', 'deleted', 'completed')
                ORDER BY allocation_id, created_at DESC, id DESC
            )
            UPDATE nurse_shift_bed_allocations AS allocation
            SET status = CASE
                WHEN allocation.is_active IS TRUE THEN 'active'
                WHEN event.action = 'completed' THEN 'completed'
                WHEN event.action = 'deactivated'
                     AND COALESCE(event.remarks, '') ILIKE 'Auto-expired:%'
                    THEN 'completed'
                ELSE 'deactivated'
            END
            FROM latest_status_event AS event
            WHERE event.allocation_id = allocation.id
              AND allocation.status IS NULL
            """
        )
    )
    # Rows without a corresponding history event receive a conservative state.
    op.execute(
        sa.text(
            """
            UPDATE nurse_shift_bed_allocations
            SET status = CASE
                WHEN is_active IS TRUE THEN 'active'
                ELSE 'deactivated'
            END
            WHERE status IS NULL
            """
        )
    )

    op.alter_column(
        "nurse_shift_bed_allocations",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.create_index(
        "ix_nurse_shift_bed_allocations_status",
        "nurse_shift_bed_allocations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_nurse_shift_bed_allocations_ended_at",
        "nurse_shift_bed_allocations",
        ["ended_at"],
        unique=False,
    )

    # Actor names are snapshots. Keep the column nullable for legacy/system
    # history rows whose actor cannot be identified.
    op.add_column(
        "nurse_shift_bed_allocation_history",
        sa.Column("actor_name", sa.String(length=200), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE nurse_shift_bed_allocation_history AS history
            SET actor_name = NULLIF(
                CONCAT_WS(
                    ' ',
                    NULLIF(BTRIM(users.first_name), ''),
                    NULLIF(BTRIM(users.last_name), '')
                ),
                ''
            )
            FROM users
            WHERE history.actor_id = users.id
              AND history.actor_name IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE nurse_shift_bed_allocation_history
            SET actor_name = 'System'
            WHERE actor_name IS NULL
              AND actor_id IS NULL
              AND (
                  action = 'completed'
                  OR COALESCE(remarks, '') ILIKE 'Auto-expired:%'
              )
            """
        )
    )


def downgrade() -> None:
    # Downgrade removes the newly-added data. Use only when intentionally
    # reverting this migration and after taking an appropriate database backup.
    op.drop_column("nurse_shift_bed_allocation_history", "actor_name")
    op.drop_index(
        "ix_nurse_shift_bed_allocations_ended_at",
        table_name="nurse_shift_bed_allocations",
    )
    op.drop_index(
        "ix_nurse_shift_bed_allocations_status",
        table_name="nurse_shift_bed_allocations",
    )
    op.drop_column("nurse_shift_bed_allocations", "ended_at")
    op.drop_column("nurse_shift_bed_allocations", "status")
