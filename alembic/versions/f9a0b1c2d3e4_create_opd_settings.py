"""create opd_settings table

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "opd_settings" in inspector.get_table_names():
        return

    op.create_table(
        "opd_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("allow_patient_delete", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "allow_appointment_delete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "allow_unpaid_bill_delete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "require_admin_approval_for_delete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed singleton row with backward-compatible defaults (deletes allowed).
    op.execute(
        sa.text(
            """
            INSERT INTO opd_settings (
                id,
                allow_patient_delete,
                allow_appointment_delete,
                allow_unpaid_bill_delete,
                require_admin_approval_for_delete,
                extra,
                updated_at
            ) VALUES (
                1, true, true, true, true, '{}'::jsonb, NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "opd_settings" not in inspector.get_table_names():
        return
    op.drop_table("opd_settings")
