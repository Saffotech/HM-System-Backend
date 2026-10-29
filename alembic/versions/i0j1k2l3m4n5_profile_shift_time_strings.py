"""convert profile shift times from TIME to VARCHAR

Revision ID: i0j1k2l3m4n5
Revises: h0i1j2k3l4m5
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, Sequence[str], None] = "h0i1j2k3l4m5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROFILE_TABLES = (
    "doctor_profiles",
    "nurse_profiles",
    "lab_technician_profiles",
    "receptionist_profiles",
    "pharmacist_profiles",
    "admin_profiles",
    "super_admin_profiles",
    "opd_billing_profiles",
)


def _time_column_type(inspector: sa.Inspector, table: str, column: str) -> str | None:
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col["type"].__class__.__name__.upper()
    return None


def _convert_shift_time_columns(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return

    for column in ("shift_start_time", "shift_end_time"):
        col_type = _time_column_type(inspector, table, column)
        if col_type == "TIME":
            op.alter_column(
                table,
                column,
                type_=sa.String(length=10),
                existing_type=sa.Time(),
                postgresql_using=(
                    f"CASE WHEN {column} IS NULL THEN NULL "
                    f"ELSE TO_CHAR({column}, 'HH24:MI') END"
                ),
            )


def upgrade() -> None:
    for table in _PROFILE_TABLES:
        _convert_shift_time_columns(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _PROFILE_TABLES:
        if table not in inspector.get_table_names():
            continue
        for column in ("shift_start_time", "shift_end_time"):
            col_type = _time_column_type(inspector, table, column)
            if col_type in {"VARCHAR", "STRING"}:
                op.alter_column(
                    table,
                    column,
                    type_=sa.Time(),
                    existing_type=sa.String(length=10),
                    postgresql_using=(
                        f"CASE WHEN {column} IS NULL OR {column} = '' THEN NULL "
                        f"ELSE {column}::time END"
                    ),
                )
