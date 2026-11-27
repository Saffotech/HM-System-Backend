"""Patient-uploaded reports (My Uploads).

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, Sequence[str], None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "patient_uploaded_reports" in tables:
        return
    op.create_table(
        "patient_uploaded_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("report_file", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patient_uploaded_reports_id", "patient_uploaded_reports", ["id"])
    op.create_index(
        "ix_patient_uploaded_reports_tenant_id",
        "patient_uploaded_reports",
        ["tenant_id"],
    )
    op.create_index(
        "ix_patient_uploaded_reports_patient_id",
        "patient_uploaded_reports",
        ["patient_id"],
    )
    op.create_index(
        "ix_patient_uploaded_reports_uploaded_by_user_id",
        "patient_uploaded_reports",
        ["uploaded_by_user_id"],
    )
    op.create_index(
        "ix_patient_uploaded_reports_created_at",
        "patient_uploaded_reports",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("patient_uploaded_reports")
