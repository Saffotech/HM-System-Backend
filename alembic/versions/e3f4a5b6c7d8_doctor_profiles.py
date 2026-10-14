"""create doctor_profiles table; add personal fields on users; backfill doctors

Revision ID: e3f4a5b6c7d8
Revises: a7b8c9d0e1f2, d2e3f4a5b6c7
Create Date: 2026-07-08

Merges the doctor-schedule branch and hospital-settings branch into one head,
then creates doctor_profiles.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = ("a7b8c9d0e1f2", "d2e3f4a5b6c7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "date_of_birth" not in user_cols:
        op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    if "emergency_contact_phone" not in user_cols:
        op.add_column(
            "users",
            sa.Column("emergency_contact_phone", sa.String(length=20), nullable=True),
        )

    if "doctor_profiles" not in inspector.get_table_names():
        op.create_table(
            "doctor_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("qualification", sa.String(length=255), nullable=True),
            sa.Column("medical_license_number", sa.String(length=100), nullable=True),
            sa.Column("experience_years", sa.Integer(), nullable=True),
            sa.Column("consultation_fee", sa.Float(), nullable=True),
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
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index(
            op.f("ix_doctor_profiles_id"),
            "doctor_profiles",
            ["id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_doctor_profiles_user_id"),
            "doctor_profiles",
            ["user_id"],
            unique=True,
        )

    # Backfill empty profiles for existing doctors
    op.execute(
        sa.text(
            """
            INSERT INTO doctor_profiles (user_id, languages, is_profile_completed, created_at, updated_at)
            SELECT u.id, '[]'::jsonb, FALSE, NOW(), NOW()
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.name = 'doctor'
              AND u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM doctor_profiles dp WHERE dp.user_id = u.id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "doctor_profiles" in inspector.get_table_names():
        op.drop_index(op.f("ix_doctor_profiles_user_id"), table_name="doctor_profiles")
        op.drop_index(op.f("ix_doctor_profiles_id"), table_name="doctor_profiles")
        op.drop_table("doctor_profiles")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "emergency_contact_phone" in user_cols:
        op.drop_column("users", "emergency_contact_phone")
    if "date_of_birth" in user_cols:
        op.drop_column("users", "date_of_birth")
