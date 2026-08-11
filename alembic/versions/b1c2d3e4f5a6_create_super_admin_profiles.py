"""Create super_admin_profiles table and backfill existing super admins.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "super_admin_profiles" not in inspector.get_table_names():
        op.create_table(
            "super_admin_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.String(length=50), nullable=True),
            sa.Column("joining_date", sa.Date(), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column(
                "languages",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
            sa.Column("profile_image", sa.String(length=500), nullable=True),
            sa.Column(
                "is_profile_completed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
            sa.UniqueConstraint("employee_id"),
        )
        op.create_index(
            op.f("ix_super_admin_profiles_id"),
            "super_admin_profiles",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_super_admin_profiles_user_id"),
            "super_admin_profiles",
            ["user_id"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            INSERT INTO super_admin_profiles (
                user_id, languages, is_profile_completed, created_at, updated_at
            )
            SELECT u.id, '[]'::jsonb, false, NOW(), NOW()
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = 'super_admin'
              AND u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM super_admin_profiles sap WHERE sap.user_id = u.id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "super_admin_profiles" in inspector.get_table_names():
        op.drop_index(
            op.f("ix_super_admin_profiles_user_id"),
            table_name="super_admin_profiles",
        )
        op.drop_index(
            op.f("ix_super_admin_profiles_id"),
            table_name="super_admin_profiles",
        )
        op.drop_table("super_admin_profiles")
