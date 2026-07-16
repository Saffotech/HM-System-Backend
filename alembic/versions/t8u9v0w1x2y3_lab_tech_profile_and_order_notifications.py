"""Create lab_technician_profiles if missing + lab order notification types.

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-07-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "t8u9v0w1x2y3"
down_revision: Union[str, Sequence[str], None] = "s7t8u9v0w1x2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "lab_technician_profiles" not in inspector.get_table_names():
        op.create_table(
            "lab_technician_profiles",
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
            op.f("ix_lab_technician_profiles_id"),
            "lab_technician_profiles",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_lab_technician_profiles_user_id"),
            "lab_technician_profiles",
            ["user_id"],
            unique=False,
        )

        op.execute(
            sa.text(
                """
                INSERT INTO lab_technician_profiles (
                    user_id, languages, is_profile_completed, created_at, updated_at
                )
                SELECT u.id, '[]'::jsonb, false, NOW(), NOW()
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE r.name = 'lab_technician'
                  AND u.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM lab_technician_profiles lp WHERE lp.user_id = u.id
                  )
                """
            )
        )

    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LAB_ORDER_CREATED'"
    )
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'LAB_ORDER_CANCELLED'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lab_technician_profiles" in inspector.get_table_names():
        op.drop_index(
            op.f("ix_lab_technician_profiles_user_id"),
            table_name="lab_technician_profiles",
        )
        op.drop_index(
            op.f("ix_lab_technician_profiles_id"),
            table_name="lab_technician_profiles",
        )
        op.drop_table("lab_technician_profiles")
