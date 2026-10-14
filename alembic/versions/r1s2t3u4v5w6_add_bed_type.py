"""Add bed_type to beds (single / double).

Revision ID: r1s2t3u4v5w6
Revises: p9q0r1s2t3u4
Create Date: 2026-09-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, Sequence[str], None] = "p9q0r1s2t3u4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "beds" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("beds")}
    if "bed_type" not in columns:
        op.add_column(
            "beds",
            sa.Column("bed_type", sa.String(length=20), nullable=False, server_default="single"),
        )
        op.alter_column("beds", "bed_type", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "beds" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("beds")}
    if "bed_type" in columns:
        op.drop_column("beds", "bed_type")
