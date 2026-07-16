"""Rename registration_number to license_number.

Revision ID: s7t8u9v0w1x2
Revises: 0fd72e123992
Create Date: 2026-07-16

Renames registration_number -> license_number on hospital_settings,
nurse_profiles, and lab_technician_profiles (when present).
Safe for DBs that already have license_number (e.g. fresh installs
after create migrations were updated).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s7t8u9v0w1x2"
down_revision: Union[str, Sequence[str], None] = "0fd72e123992"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "hospital_settings",
    "nurse_profiles",
    "lab_technician_profiles",
)


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _rename_if_needed(table_name: str, old: str, new: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    columns = _column_names(inspector, table_name)
    if old in columns and new not in columns:
        op.alter_column(table_name, old, new_column_name=new)


def upgrade() -> None:
    for table in _TABLES:
        _rename_if_needed(table, "registration_number", "license_number")


def downgrade() -> None:
    for table in _TABLES:
        _rename_if_needed(table, "license_number", "registration_number")
