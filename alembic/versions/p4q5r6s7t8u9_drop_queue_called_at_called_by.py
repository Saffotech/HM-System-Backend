"""Drop patient_queue called_at and called_by columns.

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-07-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p4q5r6s7t8u9"
down_revision: Union[str, Sequence[str], None] = "o3p4q5r6s7t8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_names(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def _fk_names(inspector, table: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table) if fk.get("name")}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "patient_queue"):
        return

    cols = _column_names(inspector, "patient_queue")
    fks = _fk_names(inspector, "patient_queue")

    if "fk_patient_queue_called_by_users" in fks:
        op.drop_constraint(
            "fk_patient_queue_called_by_users",
            "patient_queue",
            type_="foreignkey",
        )

    if "called_by" in cols:
        op.drop_column("patient_queue", "called_by")
    if "called_at" in cols:
        op.drop_column("patient_queue", "called_at")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "patient_queue"):
        return

    cols = _column_names(inspector, "patient_queue")

    if "called_at" not in cols:
        op.add_column(
            "patient_queue",
            sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "called_by" not in cols:
        op.add_column(
            "patient_queue",
            sa.Column("called_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_patient_queue_called_by_users",
            "patient_queue",
            "users",
            ["called_by"],
            ["id"],
        )
