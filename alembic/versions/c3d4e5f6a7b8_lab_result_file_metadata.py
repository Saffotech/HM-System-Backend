"""lab results file metadata and history index

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("lab_results")}

    if "file_name" not in columns:
        op.add_column(
            "lab_results",
            sa.Column("file_name", sa.String(length=255), nullable=True),
        )
    if "file_type" not in columns:
        op.add_column(
            "lab_results",
            sa.Column("file_type", sa.String(length=100), nullable=True),
        )
    if "file_size" not in columns:
        op.add_column(
            "lab_results",
            sa.Column("file_size", sa.Integer(), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("lab_results")}
    if "ix_lab_results_created_at" not in indexes:
        op.create_index(
            "ix_lab_results_created_at",
            "lab_results",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_lab_results_created_at", table_name="lab_results")
    op.drop_column("lab_results", "file_size")
    op.drop_column("lab_results", "file_type")
    op.drop_column("lab_results", "file_name")
