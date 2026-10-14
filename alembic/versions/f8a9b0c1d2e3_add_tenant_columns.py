"""Add tenants and tenant_id columns expected by the models.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-14

Existing hospital rows are attached to one default hospital so the new
non-null tenant_id columns can be filled.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# users and audit logs may exist without a hospital. Every other table is hospital-owned.
NULLABLE_TABLES = {"users", "audit_logs"}
UNIQUE_TABLES = {"hospital_settings", "opd_settings"}
TABLES = (
    "users",
    "audit_logs",
    "departments",
    "patients",
    "opd_visits",
    "appointments",
    "beds",
    "prescriptions",
    "lab_tests",
    "lab_test_orders",
    "lab_results",
    "patient_queue",
    "dispensings",
    "notifications",
    "ipd_admissions",
    "nurse_doctor_visits",
    "nurse_workforce_shifts",
    "nurse_shift_bed_allocations",
    "shift_handovers",
    "patient_vitals",
    "patient_other_visits",
    "nursing_notes",
    "medication_administrations",
    "hospital_settings",
    "opd_settings",
)


def _ensure_tenants_table() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tenants" in inspector.get_table_names():
        return

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("hospital_type", sa.String(length=50), nullable=False, server_default="General"),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_tenants_code"),
        sa.UniqueConstraint("email", name="uq_tenants_email"),
    )
    op.create_index("ix_tenants_id", "tenants", ["id"])
    op.create_index("ix_tenants_code", "tenants", ["code"])
    op.create_index("ix_tenants_email", "tenants", ["email"])


def _ensure_default_hospital() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (name, code, hospital_type, is_active, created_at, updated_at)
            SELECT 'Default Hospital', 'DEFAULT', 'General', TRUE, NOW(), NOW()
            WHERE NOT EXISTS (SELECT 1 FROM tenants)
            """
        )
    )


def _add_tenant_column(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns(table)}
    if "tenant_id" not in columns:
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            f'UPDATE "{table}" SET tenant_id = (SELECT id FROM tenants ORDER BY id LIMIT 1) '
            "WHERE tenant_id IS NULL"
        )
    )

    if table not in NULLABLE_TABLES:
        still_nullable = "tenant_id" not in columns or columns["tenant_id"]["nullable"]
        if still_nullable:
            op.alter_column(table, "tenant_id", existing_type=sa.Integer(), nullable=False)

    index_name = f"ix_{table}_tenant_id"
    indexes = {index["name"] for index in inspector.get_indexes(table)}
    if index_name not in indexes:
        unique = False
        if table in UNIQUE_TABLES:
            duplicate = bind.execute(
                sa.text(
                    f'SELECT 1 FROM "{table}" GROUP BY tenant_id HAVING COUNT(*) > 1 LIMIT 1'
                )
            ).first()
            unique = duplicate is None
        op.create_index(index_name, table, ["tenant_id"], unique=unique)

    fk_name = f"fk_{table}_tenant_id"
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys(table)}
    if fk_name not in foreign_keys:
        op.create_foreign_key(fk_name, table, "tenants", ["tenant_id"], ["id"])


def upgrade() -> None:
    _ensure_tenants_table()
    _ensure_default_hospital()
    for table in TABLES:
        _add_tenant_column(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    for table in TABLES:
        if table not in existing:
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys(table)}
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        fk_name = f"fk_{table}_tenant_id"
        index_name = f"ix_{table}_tenant_id"
        if fk_name in foreign_keys:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        if index_name in indexes:
            op.drop_index(index_name, table_name=table)
        if "tenant_id" in columns:
            op.drop_column(table, "tenant_id")

    if "tenants" in existing:
        op.drop_table("tenants")
