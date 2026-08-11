"""Add department_id to lab_test_orders for Laboratory vs Radiology routing.

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-08-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v0w1x2y3z4a5"
down_revision: Union[str, Sequence[str], None] = "u9v0w1x2y3z4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def _ensure_lab_departments(conn) -> tuple[int, int]:
    """Return (lab_id, rad_id), creating rows if missing."""
    for code, name in (("LAB", "Laboratory"), ("RAD", "Radiology")):
        exists = conn.execute(
            sa.text("SELECT id FROM departments WHERE code = :code LIMIT 1"),
            {"code": code},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO departments (name, code, is_active) "
                    "VALUES (:name, :code, true)"
                ),
                {"name": name, "code": code},
            )

    lab = conn.execute(
        sa.text("SELECT id FROM departments WHERE code = 'LAB' LIMIT 1")
    ).fetchone()
    rad = conn.execute(
        sa.text("SELECT id FROM departments WHERE code = 'RAD' LIMIT 1")
    ).fetchone()
    if not lab or not rad:
        raise RuntimeError("Failed to ensure LAB/RAD departments")
    return int(lab[0]), int(rad[0])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "lab_test_orders"):
        return

    lab_id, rad_id = _ensure_lab_departments(bind)

    if not _column_exists(inspector, "lab_test_orders", "department_id"):
        op.add_column(
            "lab_test_orders",
            sa.Column("department_id", sa.Integer(), nullable=True),
        )

    # Backfill: Radiology category/test names → RAD; everything else → LAB
    bind.execute(
        sa.text(
            """
            UPDATE lab_test_orders
            SET department_id = :rad_id
            WHERE department_id IS NULL
              AND (
                lower(coalesce(category, '')) LIKE '%radiolog%'
                OR lower(coalesce(category, '')) LIKE '%imaging%'
                OR lower(coalesce(test_name, '')) LIKE '%x-ray%'
                OR lower(coalesce(test_name, '')) LIKE '%xray%'
                OR lower(coalesce(test_name, '')) LIKE '%mri%'
                OR lower(coalesce(test_name, '')) LIKE '%ct scan%'
                OR lower(coalesce(test_name, '')) LIKE '%ultrasound%'
                OR lower(coalesce(test_name, '')) LIKE '%usg%'
                OR lower(coalesce(test_name, '')) LIKE '%mammograph%'
              )
            """
        ),
        {"rad_id": rad_id},
    )
    bind.execute(
        sa.text(
            """
            UPDATE lab_test_orders
            SET department_id = :lab_id
            WHERE department_id IS NULL
            """
        ),
        {"lab_id": lab_id},
    )

    inspector = sa.inspect(bind)
    fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("lab_test_orders")
    }
    indexes = {idx["name"] for idx in inspector.get_indexes("lab_test_orders")}

    op.alter_column(
        "lab_test_orders",
        "department_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    if "fk_lab_test_orders_department_id" not in fks:
        op.create_foreign_key(
            "fk_lab_test_orders_department_id",
            "lab_test_orders",
            "departments",
            ["department_id"],
            ["id"],
        )

    if "ix_lab_test_orders_department_id" not in indexes:
        op.create_index(
            "ix_lab_test_orders_department_id",
            "lab_test_orders",
            ["department_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "lab_test_orders"):
        return
    if not _column_exists(inspector, "lab_test_orders", "department_id"):
        return

    fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("lab_test_orders")
    }
    indexes = {idx["name"] for idx in inspector.get_indexes("lab_test_orders")}

    if "ix_lab_test_orders_department_id" in indexes:
        op.drop_index(
            "ix_lab_test_orders_department_id",
            table_name="lab_test_orders",
        )
    if "fk_lab_test_orders_department_id" in fks:
        op.drop_constraint(
            "fk_lab_test_orders_department_id",
            "lab_test_orders",
            type_="foreignkey",
        )
    op.drop_column("lab_test_orders", "department_id")
