"""Store prescription item duration as text (e.g. '3 days').

Revision ID: s7t8u9v0w1x2
Revises: r6s7t8u9v0w1
Create Date: 2026-08-10

Doctor module duration UI sends value + unit; schema/DB must keep the full string.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s7t8u9v0w1x2"
down_revision: Union[str, Sequence[str], None] = "r6s7t8u9v0w1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_type_name(inspector, table: str, column: str) -> str | None:
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return str(col["type"]).lower()
    return None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "prescription_items"):
        return

    type_name = _column_type_name(inspector, "prescription_items", "duration")
    if type_name is None:
        return

    # Already text/varchar — nothing to do.
    if any(token in type_name for token in ("char", "text", "string")):
        return

    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute(
            "ALTER TABLE prescription_items "
            "ALTER COLUMN duration TYPE VARCHAR(50) "
            "USING TRIM(duration::text)"
        )
    else:
        with op.batch_alter_table("prescription_items") as batch_op:
            batch_op.alter_column(
                "duration",
                existing_type=sa.Integer(),
                type_=sa.String(length=50),
                existing_nullable=False,
                postgresql_using="TRIM(duration::text)",
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "prescription_items"):
        return

    type_name = _column_type_name(inspector, "prescription_items", "duration")
    if type_name is None:
        return
    if "int" in type_name:
        return

    dialect = conn.dialect.name
    if dialect == "postgresql":
        # Keep leading digits only so downgrade does not fail on '3 days'.
        op.execute(
            """
            ALTER TABLE prescription_items
            ALTER COLUMN duration TYPE INTEGER
            USING COALESCE(
                NULLIF(regexp_replace(duration::text, '[^0-9]', '', 'g'), ''),
                '0'
            )::integer
            """
        )
    else:
        with op.batch_alter_table("prescription_items") as batch_op:
            batch_op.alter_column(
                "duration",
                existing_type=sa.String(length=50),
                type_=sa.Integer(),
                existing_nullable=False,
            )
