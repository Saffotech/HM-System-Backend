"""ensure users country and postal_code columns exist

Revision ID: h0i1j2k3l4m5
Revises: g0h1i2j3k4l5
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h0i1j2k3l4m5"
down_revision: Union[str, Sequence[str], None] = "g0h1i2j3k4l5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "country" not in user_cols:
        op.add_column("users", sa.Column("country", sa.String(length=100), nullable=True))
    if "postal_code" not in user_cols:
        op.add_column("users", sa.Column("postal_code", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "postal_code" in user_cols:
        op.drop_column("users", "postal_code")
    if "country" in user_cols:
        op.drop_column("users", "country")
