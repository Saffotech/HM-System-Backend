"""add hospital_settings table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hospital_settings" in inspector.get_table_names():
        return

    op.create_table(
        "hospital_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tagline", sa.String(length=300), nullable=True),
        sa.Column("address_line1", sa.String(length=300), nullable=True),
        sa.Column("address_line2", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("gstin", sa.String(length=20), nullable=True),
        sa.Column("pan", sa.String(length=20), nullable=True),
        sa.Column("registration_number", sa.String(length=100), nullable=True),
        sa.Column("default_registration_fee", sa.Float(), nullable=False),
        sa.Column("default_consultation_fee", sa.Float(), nullable=False),
        sa.Column("default_gst_percent", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hospital_settings" not in inspector.get_table_names():
        return
    op.drop_table("hospital_settings")
