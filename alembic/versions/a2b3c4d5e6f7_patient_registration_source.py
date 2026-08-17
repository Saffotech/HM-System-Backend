"""Add patients.registration_source (OPD | IPD).

Revision ID: a2b3c4d5e6f7
Revises: w1x2y3z4a5b6, g0a1b2c3d4e5
Create Date: 2026-08-14

Nullable add → backfill → NOT NULL → CHECK. Existing rows stay deploy-safe.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = ("w1x2y3z4a5b6", "g0a1b2c3d4e5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "ck_patients_registration_source"
COLUMN_NAME = "registration_source"


def _column_exists(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _column_exists(inspector, "patients", COLUMN_NAME):
        op.add_column(
            "patients",
            sa.Column(COLUMN_NAME, sa.String(length=3), nullable=True),
        )

    op.execute(
        sa.text(
            """
            UPDATE patients
            SET registration_source = 'IPD'
            WHERE registration_source IS NULL
              AND registered_by IN (
                  SELECT u.id
                  FROM users u
                  JOIN roles r ON r.id = u.role_id
                  WHERE r.name = 'ipd'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE patients
            SET registration_source = 'OPD'
            WHERE registration_source IS NULL
            """
        )
    )

    op.alter_column(
        "patients",
        COLUMN_NAME,
        existing_type=sa.String(length=3),
        nullable=False,
    )

    inspector = sa.inspect(conn)
    existing_checks = {
        ck["name"]
        for ck in inspector.get_check_constraints("patients")
        if ck.get("name")
    }
    if CONSTRAINT_NAME not in existing_checks:
        op.create_check_constraint(
            CONSTRAINT_NAME,
            "patients",
            "registration_source IN ('OPD', 'IPD')",
        )

    indexes = {
        ix["name"] for ix in inspector.get_indexes("patients") if ix.get("name")
    }
    if "ix_patients_registration_source" not in indexes:
        op.create_index(
            "ix_patients_registration_source",
            "patients",
            [COLUMN_NAME],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    indexes = {
        ix["name"] for ix in inspector.get_indexes("patients") if ix.get("name")
    }
    if "ix_patients_registration_source" in indexes:
        op.drop_index("ix_patients_registration_source", table_name="patients")

    existing_checks = {
        ck["name"]
        for ck in inspector.get_check_constraints("patients")
        if ck.get("name")
    }
    if CONSTRAINT_NAME in existing_checks:
        op.drop_constraint(CONSTRAINT_NAME, "patients", type_="check")

    if _column_exists(inspector, "patients", COLUMN_NAME):
        op.drop_column("patients", COLUMN_NAME)
