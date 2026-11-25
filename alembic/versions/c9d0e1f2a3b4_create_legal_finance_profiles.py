"""Create legal_finance_profiles.

Revision ID: c9d0e1f2a3b4
Revises: h2i3j4k5l6m7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "legal_finance_profiles" in inspector.get_table_names():
        return

    op.create_table(
        "legal_finance_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("profile_image", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_legal_finance_profiles_id"),
        "legal_finance_profiles",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_finance_profiles_user_id"),
        "legal_finance_profiles",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "legal_finance_profiles" not in inspector.get_table_names():
        return
    op.drop_index(op.f("ix_legal_finance_profiles_user_id"), table_name="legal_finance_profiles")
    op.drop_index(op.f("ix_legal_finance_profiles_id"), table_name="legal_finance_profiles")
    op.drop_table("legal_finance_profiles")
