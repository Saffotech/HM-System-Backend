"""add users.specialization if missing (repair migration)

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "specialization" not in user_cols:
        op.add_column(
            "users",
            sa.Column("specialization", sa.String(length=120), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "specialization" in user_cols:
        op.drop_column("users", "specialization")
