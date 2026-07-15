"""Create receptionist_profiles table and backfill existing receptionists.

Revision ID: q5r6s7t8u9v1
Revises: q5r6s7t8u9v0
Create Date: 2026-07-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q5r6s7t8u9v1"
down_revision: Union[str, Sequence[str], None] = "q5r6s7t8u9v0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "receptionist_profiles" not in inspector.get_table_names():
        op.create_table(
            "receptionist_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.String(length=50), nullable=True),
            sa.Column("qualification", sa.String(length=255), nullable=True),
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
            sa.Column("shift_start_time", sa.Time(), nullable=True),
            sa.Column("shift_end_time", sa.Time(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
            sa.UniqueConstraint("employee_id"),
        )
        op.create_index(
            op.f("ix_receptionist_profiles_id"),
            "receptionist_profiles",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_receptionist_profiles_user_id"),
            "receptionist_profiles",
            ["user_id"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            INSERT INTO receptionist_profiles (
                user_id, languages, is_profile_completed, created_at, updated_at
            )
            SELECT u.id, '[]'::jsonb, false, NOW(), NOW()
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE r.name = 'receptionist'
              AND u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM receptionist_profiles rp WHERE rp.user_id = u.id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "receptionist_profiles" in inspector.get_table_names():
        op.drop_index(
            op.f("ix_receptionist_profiles_user_id"),
            table_name="receptionist_profiles",
        )
        op.drop_index(
            op.f("ix_receptionist_profiles_id"),
            table_name="receptionist_profiles",
        )
        op.drop_table("receptionist_profiles")
