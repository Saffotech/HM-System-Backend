"""Allow lab orders and prescriptions to attach to an IPD admission.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-18

OPD rows keep appointment_id. IPD rows use admission_id. Exactly one parent.
Prescriptions stay unique per appointment; multiple Rx per admission are allowed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ONE_PARENT_SQL = (
    "(appointment_id IS NOT NULL AND admission_id IS NULL) OR "
    "(appointment_id IS NULL AND admission_id IS NOT NULL)"
)


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _columns(inspector, table: str) -> dict:
    if not _table_exists(inspector, table):
        return {}
    return {col["name"]: col for col in inspector.get_columns(table)}


def _index_by_name(inspector, table: str) -> dict:
    if not _table_exists(inspector, table):
        return {}
    return {idx["name"]: idx for idx in inspector.get_indexes(table)}


def _fk_names(inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table) if fk.get("name")}


def _unique_constraint_names(inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    return {
        uc["name"]
        for uc in inspector.get_unique_constraints(table)
        if uc.get("name")
    }


def _check_constraint_names(inspector, table: str) -> set[str]:
    if not _table_exists(inspector, table):
        return set()
    getter = getattr(inspector, "get_check_constraints", None)
    if getter is None:
        return set()
    return {c["name"] for c in getter(table) if c.get("name")}


def _ensure_admission_id(inspector, table: str, fk_name: str, index_name: str) -> None:
    if not _table_exists(inspector, table):
        return
    if "admission_id" not in _columns(inspector, table):
        op.add_column(
            table,
            sa.Column("admission_id", sa.Integer(), nullable=True),
        )
        inspector = sa.inspect(op.get_bind())

    if fk_name not in _fk_names(inspector, table):
        op.create_foreign_key(
            fk_name,
            table,
            "ipd_admissions",
            ["admission_id"],
            ["id"],
        )
        inspector = sa.inspect(op.get_bind())

    if index_name not in _index_by_name(inspector, table):
        op.create_index(index_name, table, ["admission_id"])


def _make_appointment_id_nullable(inspector, table: str) -> None:
    col = _columns(inspector, table).get("appointment_id")
    if not col:
        return
    if col.get("nullable"):
        return
    op.alter_column(
        table,
        "appointment_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def _drop_prescription_appointment_uniques(inspector) -> None:
    table = "prescriptions"
    if not _table_exists(inspector, table):
        return

    for uc in inspector.get_unique_constraints(table):
        if uc.get("column_names") == ["appointment_id"] and uc.get("name"):
            op.drop_constraint(uc["name"], table, type_="unique")

    inspector = sa.inspect(op.get_bind())
    for idx in inspector.get_indexes(table):
        if (
            idx.get("unique")
            and idx.get("column_names") == ["appointment_id"]
            and idx.get("name")
            and idx["name"] != "uq_prescriptions_appointment_id"
        ):
            op.drop_index(idx["name"], table_name=table)


def _ensure_check(inspector, table: str, name: str) -> None:
    if not _table_exists(inspector, table):
        return
    if name in _check_constraint_names(inspector, table):
        return
    op.create_check_constraint(name, table, ONE_PARENT_SQL)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _ensure_admission_id(
        inspector,
        "lab_test_orders",
        "fk_lab_test_orders_admission_id",
        "ix_lab_test_orders_admission_id",
    )
    inspector = sa.inspect(bind)
    _make_appointment_id_nullable(inspector, "lab_test_orders")
    inspector = sa.inspect(bind)
    _ensure_check(inspector, "lab_test_orders", "ck_lab_test_orders_one_parent")

    inspector = sa.inspect(bind)
    _ensure_admission_id(
        inspector,
        "prescriptions",
        "fk_prescriptions_admission_id",
        "ix_prescriptions_admission_id",
    )
    inspector = sa.inspect(bind)
    _make_appointment_id_nullable(inspector, "prescriptions")
    inspector = sa.inspect(bind)
    _drop_prescription_appointment_uniques(inspector)
    inspector = sa.inspect(bind)
    indexes = _index_by_name(inspector, "prescriptions")
    if "uq_prescriptions_appointment_id" not in indexes:
        op.create_index(
            "uq_prescriptions_appointment_id",
            "prescriptions",
            ["appointment_id"],
            unique=True,
            postgresql_where=sa.text("appointment_id IS NOT NULL"),
        )
    inspector = sa.inspect(bind)
    _ensure_check(inspector, "prescriptions", "ck_prescriptions_one_parent")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "prescriptions"):
        nulls = bind.execute(
            sa.text(
                "SELECT 1 FROM prescriptions WHERE appointment_id IS NULL LIMIT 1"
            )
        ).first()
        if nulls:
            raise RuntimeError(
                "Cannot downgrade: prescriptions with admission_id still exist"
            )
        if "ck_prescriptions_one_parent" in _check_constraint_names(inspector, "prescriptions"):
            op.drop_constraint(
                "ck_prescriptions_one_parent",
                "prescriptions",
                type_="check",
            )
        indexes = _index_by_name(inspector, "prescriptions")
        if "uq_prescriptions_appointment_id" in indexes:
            op.drop_index(
                "uq_prescriptions_appointment_id",
                table_name="prescriptions",
            )
        inspector = sa.inspect(bind)
        fks = _fk_names(inspector, "prescriptions")
        indexes = _index_by_name(inspector, "prescriptions")
        if "ix_prescriptions_admission_id" in indexes:
            op.drop_index("ix_prescriptions_admission_id", table_name="prescriptions")
        if "fk_prescriptions_admission_id" in fks:
            op.drop_constraint(
                "fk_prescriptions_admission_id",
                "prescriptions",
                type_="foreignkey",
            )
        inspector = sa.inspect(bind)
        if "admission_id" in _columns(inspector, "prescriptions"):
            op.drop_column("prescriptions", "admission_id")
        inspector = sa.inspect(bind)
        if "appointment_id" in _columns(inspector, "prescriptions"):
            op.alter_column(
                "prescriptions",
                "appointment_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
            inspector = sa.inspect(bind)
            if "ix_prescriptions_appointment_id" not in _index_by_name(inspector, "prescriptions"):
                op.create_index(
                    "ix_prescriptions_appointment_id",
                    "prescriptions",
                    ["appointment_id"],
                    unique=True,
                )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "lab_test_orders"):
        nulls = bind.execute(
            sa.text(
                "SELECT 1 FROM lab_test_orders WHERE appointment_id IS NULL LIMIT 1"
            )
        ).first()
        if nulls:
            raise RuntimeError(
                "Cannot downgrade: lab_test_orders with admission_id still exist"
            )
        if "ck_lab_test_orders_one_parent" in _check_constraint_names(inspector, "lab_test_orders"):
            op.drop_constraint(
                "ck_lab_test_orders_one_parent",
                "lab_test_orders",
                type_="check",
            )
        inspector = sa.inspect(bind)
        fks = _fk_names(inspector, "lab_test_orders")
        indexes = _index_by_name(inspector, "lab_test_orders")
        if "ix_lab_test_orders_admission_id" in indexes:
            op.drop_index(
                "ix_lab_test_orders_admission_id",
                table_name="lab_test_orders",
            )
        if "fk_lab_test_orders_admission_id" in fks:
            op.drop_constraint(
                "fk_lab_test_orders_admission_id",
                "lab_test_orders",
                type_="foreignkey",
            )
        inspector = sa.inspect(bind)
        if "admission_id" in _columns(inspector, "lab_test_orders"):
            op.drop_column("lab_test_orders", "admission_id")
        inspector = sa.inspect(bind)
        if "appointment_id" in _columns(inspector, "lab_test_orders"):
            op.alter_column(
                "lab_test_orders",
                "appointment_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
