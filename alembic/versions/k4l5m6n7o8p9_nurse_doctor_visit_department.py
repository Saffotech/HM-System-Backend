"""Add department snapshot to nurse_doctor_visits.

Revision ID: k4l5m6n7o8p9
Revises: 91445aa645ea
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, Sequence[str], None] = "91445aa645ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def _fk_exists(inspector, table: str, name: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return any(fk.get("name") == name for fk in inspector.get_foreign_keys(table))


def _index_exists(inspector, table: str, name: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return any(idx.get("name") == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "nurse_doctor_visits"):
        return

    if not _column_exists(inspector, "nurse_doctor_visits", "department_id"):
        op.add_column(
            "nurse_doctor_visits",
            sa.Column("department_id", sa.Integer(), nullable=True),
        )
    if not _column_exists(inspector, "nurse_doctor_visits", "department_name"):
        op.add_column(
            "nurse_doctor_visits",
            sa.Column("department_name", sa.String(length=255), nullable=True),
        )

    inspector = sa.inspect(bind)
    fk_name = "fk_nurse_doctor_visits_department_id"
    if not _fk_exists(inspector, "nurse_doctor_visits", fk_name):
        op.create_foreign_key(
            fk_name,
            "nurse_doctor_visits",
            "departments",
            ["department_id"],
            ["id"],
        )

    idx_name = "ix_nurse_doctor_visits_department_id"
    if not _index_exists(inspector, "nurse_doctor_visits", idx_name):
        op.create_index(idx_name, "nurse_doctor_visits", ["department_id"])

    bind.execute(
        sa.text(
            """
            UPDATE nurse_doctor_visits AS visit
            SET department_id = doctor.department_id,
                department_name = dept.name
            FROM users AS doctor
            LEFT JOIN departments AS dept ON dept.id = doctor.department_id
            WHERE visit.doctor_id = doctor.id
              AND visit.department_id IS NULL
              AND doctor.department_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "nurse_doctor_visits"):
        return

    idx_name = "ix_nurse_doctor_visits_department_id"
    if _index_exists(inspector, "nurse_doctor_visits", idx_name):
        op.drop_index(idx_name, table_name="nurse_doctor_visits")

    fk_name = "fk_nurse_doctor_visits_department_id"
    if _fk_exists(inspector, "nurse_doctor_visits", fk_name):
        op.drop_constraint(fk_name, "nurse_doctor_visits", type_="foreignkey")

    if _column_exists(inspector, "nurse_doctor_visits", "department_name"):
        op.drop_column("nurse_doctor_visits", "department_name")
    if _column_exists(inspector, "nurse_doctor_visits", "department_id"):
        op.drop_column("nurse_doctor_visits", "department_id")
