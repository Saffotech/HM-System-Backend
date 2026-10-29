"""Align labteststatus PG enum with LabTestStatus .value strings.

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
Create Date: 2026-08-11

SQLAlchemy Enum(LabTestStatus) without values_callable used member NAMES
(ORDERED, COMPLETED, …) while the DB/API use lowercase values
(ordered, completed, …). Normalize labels and row data to lowercase values.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u9v0w1x2y3z4"
down_revision: Union[str, Sequence[str], None] = "t8u9v0w1x2y3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_VALUES = (
    "ordered",
    "sample_collected",
    "completed",
    "cancelled",
)


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


def _normalize_status_text(conn) -> None:
    """Map enum names / legacy labels to Option B lowercase values."""
    conn.execute(
        sa.text(
            """
            UPDATE lab_test_orders
            SET status = CASE lower(status)
                WHEN 'ordered' THEN 'ordered'
                WHEN 'sample_collected' THEN 'sample_collected'
                WHEN 'processing' THEN 'sample_collected'
                WHEN 'completed' THEN 'completed'
                WHEN 'cancelled' THEN 'cancelled'
                WHEN 'canceled' THEN 'cancelled'
                ELSE lower(status)
            END
            """
        )
    )
    # Any leftover unknown values: keep lowercase; migration will fail loudly if invalid.
    conn.execute(sa.text("UPDATE lab_test_orders SET status = lower(status)"))


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
        _normalize_status_text(conn)

        # Drop old enum (may still have NAME-style labels).
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
        labels = ", ".join(f"'{v}'" for v in STATUS_VALUES)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({labels})")
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

    _normalize_status_text(conn)


def downgrade() -> None:
    # Irreversible in a meaningful way: values stay lowercase which is correct.
    pass
