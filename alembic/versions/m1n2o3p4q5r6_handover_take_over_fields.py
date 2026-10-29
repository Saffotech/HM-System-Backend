"""Add replacement nurse / take-over fields on shift_handovers.

Revision ID: m1n2o3p4q5r6
Revises: l0f1a2b3c4d5
Create Date: 2026-07-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, Sequence[str], None] = "l0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "shift_handovers" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("shift_handovers")}

    if "replacement_nurse_id" not in columns:
        op.add_column(
            "shift_handovers",
            sa.Column("replacement_nurse_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_shift_handovers_replacement_nurse_id",
            "shift_handovers",
            ["replacement_nurse_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_shift_handovers_replacement_nurse_id_users",
            "shift_handovers",
            "users",
            ["replacement_nurse_id"],
            ["id"],
        )

    if "taken_over_at" not in columns:
        op.add_column(
            "shift_handovers",
            sa.Column("taken_over_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "take_over_notes" not in columns:
        op.add_column(
            "shift_handovers",
            sa.Column("take_over_notes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "shift_handovers" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("shift_handovers")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("shift_handovers")}
    indexes = {idx["name"] for idx in inspector.get_indexes("shift_handovers")}

    if "fk_shift_handovers_replacement_nurse_id_users" in fks:
        op.drop_constraint(
            "fk_shift_handovers_replacement_nurse_id_users",
            "shift_handovers",
            type_="foreignkey",
        )

    if "ix_shift_handovers_replacement_nurse_id" in indexes:
        op.drop_index(
            "ix_shift_handovers_replacement_nurse_id",
            table_name="shift_handovers",
        )

    if "take_over_notes" in columns:
        op.drop_column("shift_handovers", "take_over_notes")

    if "taken_over_at" in columns:
        op.drop_column("shift_handovers", "taken_over_at")

    if "replacement_nurse_id" in columns:
        op.drop_column("shift_handovers", "replacement_nurse_id")
