"""Add beds.is_active for inventory soft delete.

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-11-13

Existing beds stay active. The column keeps a server default so new rows
are active when the application omits the field. Historical bed rows are
not removed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "beds" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("beds")}
    if "is_active" not in columns:
        op.add_column(
            "beds",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    indexes = {index["name"] for index in inspector.get_indexes("beds")}
    if "ix_beds_is_active" not in indexes:
        op.create_index("ix_beds_is_active", "beds", ["is_active"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "beds" not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes("beds")}
    if "ix_beds_is_active" in indexes:
        op.drop_index("ix_beds_is_active", table_name="beds")

    columns = {column["name"] for column in inspector.get_columns("beds")}
    if "is_active" in columns:
        op.drop_column("beds", "is_active")
