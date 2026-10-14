"""Create the lab test catalog.

Revision ID: labcat20260825
Revises: k4l5m6n7o8p9
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "labcat20260825"
down_revision: Union[str, Sequence[str], None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "lab_tests" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "lab_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_name", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_lab_tests_price_non_negative"),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_lab_tests_department_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "test_name",
            "department_id",
            name="uq_lab_tests_name_department",
        ),
    )
    op.create_index("ix_lab_tests_id", "lab_tests", ["id"], unique=False)
    op.create_index(
        "ix_lab_tests_department_id", "lab_tests", ["department_id"], unique=False
    )
    op.create_index("ix_lab_tests_active", "lab_tests", ["active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lab_tests_active", table_name="lab_tests")
    op.drop_index("ix_lab_tests_department_id", table_name="lab_tests")
    op.drop_index("ix_lab_tests_id", table_name="lab_tests")
    op.drop_table("lab_tests")
