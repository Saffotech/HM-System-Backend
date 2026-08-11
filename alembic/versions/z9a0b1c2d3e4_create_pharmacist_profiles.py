"""Create pharmacist_profiles table and backfill existing pharmacists.

Revision ID: z9a0b1c2d3e4
Revises: y8z9a0b1c2d3
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "z9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "y8z9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "pharmacist_profiles" not in inspector.get_table_names():
        op.create_table(
            "pharmacist_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("qualification", sa.String(length=255), nullable=True),
            sa.Column("license_number", sa.String(length=100), nullable=True),
            sa.Column("employee_id", sa.String(length=50), nullable=True),
            sa.Column("experience_years", sa.Integer(), nullable=True),
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
            sa.Column("shift_name", sa.String(length=100), nullable=True),
            sa.Column("shift_start_time", sa.String(length=10), nullable=True),
            sa.Column("shift_end_time", sa.String(length=10), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
            sa.UniqueConstraint("employee_id"),
        )
        op.create_index(
            op.f("ix_pharmacist_profiles_id"),
            "pharmacist_profiles",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_pharmacist_profiles_user_id"),
            "pharmacist_profiles",
            ["user_id"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            INSERT INTO pharmacist_profiles (
                user_id, languages, is_profile_completed, created_at, updated_at
            )
            SELECT u.id, '[]'::jsonb, false, NOW(), NOW()
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = 'pharmacist'
              AND u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM pharmacist_profiles pp WHERE pp.user_id = u.id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "pharmacist_profiles" in inspector.get_table_names():
        op.drop_index(
            op.f("ix_pharmacist_profiles_user_id"),
            table_name="pharmacist_profiles",
        )
        op.drop_index(
            op.f("ix_pharmacist_profiles_id"),
            table_name="pharmacist_profiles",
        )
        op.drop_table("pharmacist_profiles")
