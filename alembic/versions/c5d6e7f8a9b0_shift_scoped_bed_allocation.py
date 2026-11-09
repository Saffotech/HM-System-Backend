"""Allow one active nurse per bed per shift.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-11-09

Shift handover needs Morning and Evening rows active on the same bed.
Drops the one-active-row-per-bed index and restores a per-shift unique index.
Blank shift names are filled from the nurse roster when that date has one shift.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nurse_shift_bed_allocations" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("nurse_shift_bed_allocations")}
    if bind.dialect.name == "postgresql" and {
        "shift_name",
        "shift_start",
        "shift_end",
        "nurse_id",
        "shift_date",
    }.issubset(columns):
        tenant_match = (
            "AND a.tenant_id = sub.tenant_id"
            if "tenant_id" in columns
            else ""
        )
        tenant_select = ", r.tenant_id" if "tenant_id" in columns else ""
        tenant_group = ", r.tenant_id" if "tenant_id" in columns else ""
        op.execute(
            sa.text(
                f"""
                UPDATE nurse_shift_bed_allocations AS a
                SET shift_name = sub.name,
                    shift_start = COALESCE(a.shift_start, sub.start_time),
                    shift_end = COALESCE(a.shift_end, sub.end_time),
                    updated_at = NOW()
                FROM (
                    SELECT r.nurse_id,
                           r.roster_date
                           {tenant_select},
                           MIN(s.name) AS name,
                           MIN(s.start_time) AS start_time,
                           MIN(s.end_time) AS end_time
                    FROM nurse_workforce_rosters AS r
                    JOIN nurse_workforce_shifts AS s ON s.id = r.shift_id
                    WHERE r.status IN ('scheduled', 'confirmed')
                    GROUP BY r.nurse_id, r.roster_date {tenant_group}
                    HAVING COUNT(DISTINCT lower(btrim(s.name))) = 1
                ) AS sub
                WHERE a.nurse_id = sub.nurse_id
                  AND a.shift_date = sub.roster_date
                  {tenant_match}
                  AND btrim(COALESCE(a.shift_name, '')) = ''
                """
            )
        )

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS uq_active_bed_allocation"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_active_bed_shift_allocation"))
        partition = "tenant_id, bed_id, lower(btrim(shift_name))"
        if "tenant_id" not in columns:
            partition = "bed_id, lower(btrim(shift_name))"
        op.execute(
            sa.text(
                f"""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY {partition}
                               ORDER BY created_at DESC NULLS LAST, id DESC
                           ) AS rn
                    FROM nurse_shift_bed_allocations
                    WHERE is_active = true
                      AND btrim(COALESCE(shift_name, '')) <> ''
                )
                UPDATE nurse_shift_bed_allocations AS a
                SET is_active = false,
                    assigned_until = COALESCE(a.assigned_until, CURRENT_DATE),
                    updated_at = NOW()
                FROM ranked
                WHERE a.id = ranked.id
                  AND ranked.rn > 1
                """
            )
        )
        index_cols = (
            "tenant_id, bed_id, lower(btrim(shift_name))"
            if "tenant_id" in columns
            else "bed_id, lower(btrim(shift_name))"
        )
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX uq_active_bed_shift_allocation
                ON nurse_shift_bed_allocations ({index_cols})
                WHERE is_active = true
                  AND btrim(COALESCE(shift_name, '')) <> ''
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nurse_shift_bed_allocations" not in inspector.get_table_names():
        return
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP INDEX IF EXISTS uq_active_bed_shift_allocation"))
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY bed_id
                           ORDER BY created_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM nurse_shift_bed_allocations
                WHERE is_active = true
            )
            UPDATE nurse_shift_bed_allocations AS a
            SET is_active = false,
                assigned_until = COALESCE(a.assigned_until, CURRENT_DATE),
                updated_at = NOW()
            FROM ranked
            WHERE a.id = ranked.id
              AND ranked.rn > 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_active_bed_allocation
            ON nurse_shift_bed_allocations (bed_id)
            WHERE is_active = true
            """
        )
    )
