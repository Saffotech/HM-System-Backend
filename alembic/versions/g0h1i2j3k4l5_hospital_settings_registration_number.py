"""rename license_number to registration_number on settings/profile tables

Revision ID: g0h1i2j3k4l5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g0h1i2j3k4l5"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sync_registration_number(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns(table)}
    if "license_number" in columns and "registration_number" not in columns:
        op.alter_column(
            table,
            "license_number",
            new_column_name="registration_number",
        )
    elif "registration_number" not in columns:
        op.add_column(
            table,
            sa.Column("registration_number", sa.String(length=100), nullable=True),
        )


def _revert_registration_number(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns(table)}
    if "registration_number" in columns and "license_number" not in columns:
        op.alter_column(
            table,
            "registration_number",
            new_column_name="license_number",
        )


def upgrade() -> None:
    _sync_registration_number("hospital_settings")
    _sync_registration_number("nurse_profiles")


def downgrade() -> None:
    _revert_registration_number("nurse_profiles")
    _revert_registration_number("hospital_settings")
