"""Option B lab statuses: drop processing from lab_test_orders.

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-08-10

Flow is now: ordered → sample_collected → completed (+ cancelled).
Legacy "processing" rows are remapped:
  - to completed if a lab result with parameters or a report file exists
  - otherwise to sample_collected
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t8u9v0w1x2y3"
down_revision: Union[str, Sequence[str], None] = "s7t8u9v0w1x2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _pg_status_enum_name(conn) -> str:
    row = conn.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_type t ON a.atttypid = t.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = 'lab_test_orders'
              AND a.attname = 'status'
              AND a.attnum > 0
              AND NOT a.attisdropped
            LIMIT 1
            """
        )
    ).fetchone()
    if row and row[0] and row[0] not in ("varchar", "text", "character varying"):
        return row[0]
    return "labteststatus"


def _remap_processing_rows(conn) -> None:
    """Move processing → completed (if report ready) else sample_collected."""
    conn.execute(
        sa.text(
            """
            UPDATE lab_test_orders AS o
            SET status = 'completed'
            WHERE lower(status::text) = 'processing'
              AND EXISTS (
                SELECT 1
                FROM lab_results AS r
                WHERE r.lab_test_order_id = o.id
                  AND (
                    (r.report_file IS NOT NULL AND btrim(r.report_file) <> '')
                    OR EXISTS (
                      SELECT 1
                      FROM lab_result_parameters AS p
                      WHERE p.lab_result_id = r.id
                    )
                  )
              )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE lab_test_orders
            SET status = 'sample_collected'
            WHERE lower(status::text) = 'processing'
            """
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if not _table_exists(inspector, "lab_test_orders"):
        return

    if dialect == "postgresql":
        enum_name = _pg_status_enum_name(conn)
        op.execute("ALTER TABLE lab_test_orders ALTER COLUMN status DROP DEFAULT")
        op.execute(
            """
            ALTER TABLE lab_test_orders
            ALTER COLUMN status TYPE VARCHAR
            USING status::text
            """
        )
        _remap_processing_rows(conn)
        op.execute("UPDATE lab_test_orders SET status = lower(status)")

        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
        op.execute(
            f"""
            CREATE TYPE {enum_name} AS ENUM (
                'ordered',
                'sample_collected',
                'completed',
                'cancelled'
            )
            """
        )
        op.execute(
            f"""
            ALTER TABLE lab_test_orders
            ALTER COLUMN status TYPE {enum_name}
            USING status::{enum_name}
            """
        )
        op.execute(
            "ALTER TABLE lab_test_orders ALTER COLUMN status SET DEFAULT 'ordered'"
        )
        return

    # SQLite / other: column is typically VARCHAR storing enum values.
    _remap_processing_rows(conn)
    conn.execute(
        sa.text(
            """
            UPDATE lab_test_orders
            SET status = lower(status)
            WHERE status IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if not _table_exists(inspector, "lab_test_orders"):
        return

    if dialect == "postgresql":
        enum_name = _pg_status_enum_name(conn)
        op.execute("ALTER TABLE lab_test_orders ALTER COLUMN status DROP DEFAULT")
        op.execute(
            """
            ALTER TABLE lab_test_orders
            ALTER COLUMN status TYPE VARCHAR
            USING status::text
            """
        )
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
        op.execute(
            f"""
            CREATE TYPE {enum_name} AS ENUM (
                'ordered',
                'sample_collected',
                'processing',
                'completed',
                'cancelled'
            )
            """
        )
        op.execute(
            f"""
            ALTER TABLE lab_test_orders
            ALTER COLUMN status TYPE {enum_name}
            USING status::{enum_name}
            """
        )
        op.execute(
            "ALTER TABLE lab_test_orders ALTER COLUMN status SET DEFAULT 'ordered'"
        )
        return

    # No-op for non-Postgres: values already valid without processing.
