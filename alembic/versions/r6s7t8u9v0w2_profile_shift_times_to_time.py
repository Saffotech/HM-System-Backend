"""Convert doctor/nurse profile shift times from VARCHAR to TIME.

Revision ID: r6s7t8u9v0w2
Revises: q5r6s7t8u9v1
Create Date: 2026-07-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r6s7t8u9v0w2"
down_revision: Union[str, Sequence[str], None] = "q5r6s7t8u9v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHIFT_TIME_COLUMNS = ("shift_start_time", "shift_end_time")


def _column_type_name(inspector, table_name: str, column_name: str) -> str | None:
    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return column["type"].__class__.__name__.lower()
    return None


def _alter_shift_columns_to_time(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return

    for column_name in _SHIFT_TIME_COLUMNS:
        col_type = _column_type_name(inspector, table_name, column_name)
        if col_type in {"varchar", "string", "text", "char"}:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(length=10),
                type_=sa.Time(),
                postgresql_using=(
                    f"CASE WHEN {column_name} IS NULL OR TRIM({column_name}) = '' "
                    f"THEN NULL ELSE TRIM({column_name})::time END"
                ),
                existing_nullable=True,
            )


def _alter_shift_columns_to_string(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return

    for column_name in _SHIFT_TIME_COLUMNS:
        col_type = _column_type_name(inspector, table_name, column_name)
        if col_type == "time":
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.Time(),
                type_=sa.String(length=10),
                postgresql_using=(
                    f"CASE WHEN {column_name} IS NULL "
                    f"THEN NULL ELSE TO_CHAR({column_name}, 'HH24:MI') END"
                ),
                existing_nullable=True,
            )


def upgrade() -> None:
    _alter_shift_columns_to_time("doctor_profiles")
    _alter_shift_columns_to_time("nurse_profiles")


def downgrade() -> None:
    _alter_shift_columns_to_string("doctor_profiles")
    _alter_shift_columns_to_string("nurse_profiles")
