"""Ensure users profile columns required by User model.

Revision ID: s8t9u0v1w2x3
Revises: r7s8t9u0v1w2
Create Date: 2026-07-16

Adds date_of_birth / emergency contacts when missing (fixes login SELECT).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s8t9u0v1w2x3"
down_revision: Union[str, Sequence[str], None] = "r7s8t9u0v1w2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "date_of_birth" not in user_cols:
        op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    if "emergency_contact_name" not in user_cols:
        op.add_column(
            "users",
            sa.Column("emergency_contact_name", sa.String(length=120), nullable=True),
        )
    if "emergency_contact_phone" not in user_cols:
        op.add_column(
            "users",
            sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "emergency_contact_phone" in user_cols:
        op.drop_column("users", "emergency_contact_phone")
    if "emergency_contact_name" in user_cols:
        op.drop_column("users", "emergency_contact_name")
    if "date_of_birth" in user_cols:
        op.drop_column("users", "date_of_birth")
