"""Fix patient_queue.priority: queuepriority enum → VARCHAR lowercase.

Revision ID: p5q6r7s8t9u0
Revises: i0j1k2l3m4n5
Create Date: 2026-08-06

The ORM stores QueuePriority as lowercase strings (normal/urgent/emergency)
via LowercaseStrEnum (VARCHAR). Some databases still have a native Postgres
enum ``queuepriority`` with uppercase labels (NORMAL/URGENT/EMERGENCY), which
rejects inserts of ``'normal'`` during OPD patient registration / queue enqueue.

Mirrors the status remapping approach in q5r6s7t8u9v0, but leaves the column
as VARCHAR to match the model (no recreated enum).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, Sequence[str], None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _priority_udt_name(conn) -> str | None:
    row = conn.execute(
        sa.text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'patient_queue'
              AND column_name = 'priority'
            """
        )
    ).fetchone()
    return row[0] if row else None


def _enum_type_exists(conn, type_name: str) -> bool:
    row = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": type_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not _table_exists(inspector, "patient_queue"):
        return

    cols = {c["name"] for c in inspector.get_columns("patient_queue")}
    if "priority" not in cols:
        return

    dialect = conn.dialect.name
    if dialect != "postgresql":
        # Best-effort lowercase for non-Postgres (SQLite etc.).
        op.execute(
            sa.text(
                "UPDATE patient_queue SET priority = lower(priority) "
                "WHERE priority IS NOT NULL AND priority <> lower(priority)"
            )
        )
        return

    udt = _priority_udt_name(conn)
    # Native enum (queuepriority) or any USER-DEFINED priority type → VARCHAR.
    if udt and udt != "varchar" and udt != "text":
        op.execute(
            sa.text("ALTER TABLE patient_queue ALTER COLUMN priority DROP DEFAULT")
        )
        op.execute(
            sa.text(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN priority TYPE VARCHAR(32)
                USING priority::text
                """
            )
        )

    op.execute(
        sa.text(
            "UPDATE patient_queue SET priority = lower(priority) "
            "WHERE priority IS NOT NULL AND priority <> lower(priority)"
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE patient_queue
            SET priority = 'normal'
            WHERE priority IS NULL
               OR lower(priority) NOT IN ('normal', 'urgent', 'emergency')
            """
        )
    )

    op.execute(
        sa.text(
            "ALTER TABLE patient_queue ALTER COLUMN priority SET DEFAULT 'normal'"
        )
    )
    op.execute(
        sa.text("ALTER TABLE patient_queue ALTER COLUMN priority SET NOT NULL")
    )

    # Drop orphaned enum type if nothing references it anymore.
    if _enum_type_exists(conn, "queuepriority"):
        op.execute(sa.text("DROP TYPE IF EXISTS queuepriority"))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if conn.dialect.name != "postgresql":
        return
    if not _table_exists(inspector, "patient_queue"):
        return

    cols = {c["name"] for c in inspector.get_columns("patient_queue")}
    if "priority" not in cols:
        return

    op.execute(
        sa.text("ALTER TABLE patient_queue ALTER COLUMN priority DROP DEFAULT")
    )
    # Restore uppercase enum labels used by older schemas.
    op.execute(
        sa.text("UPDATE patient_queue SET priority = upper(priority)")
    )
    op.execute(sa.text("DROP TYPE IF EXISTS queuepriority"))
    op.execute(
        sa.text(
            """
            CREATE TYPE queuepriority AS ENUM (
                'NORMAL',
                'URGENT',
                'EMERGENCY'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE patient_queue
            ALTER COLUMN priority TYPE queuepriority
            USING priority::queuepriority
            """
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE patient_queue ALTER COLUMN priority SET DEFAULT 'NORMAL'"
        )
    )
