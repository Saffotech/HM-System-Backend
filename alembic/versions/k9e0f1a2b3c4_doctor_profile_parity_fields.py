"""Add missing doctor profile parity fields (string-based shift).

Revision ID: k9e0f1a2b3c4
Revises: j8d9e0f1a2b3
Create Date: 2026-07-13

- users.emergency_contact_name
- doctor_profiles.employee_id, joining_date
- doctor_profiles.shift_name, shift_start_time, shift_end_time (strings)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "j8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "emergency_contact_name" not in user_cols:
        op.add_column(
            "users",
            sa.Column("emergency_contact_name", sa.String(length=120), nullable=True),
        )

    doctor_cols = {c["name"] for c in inspector.get_columns("doctor_profiles")}

    # If an earlier draft of this revision created shift_id / shifts, clean them up.
    if "shift_id" in doctor_cols:
        fk_names = {
            fk["name"]
            for fk in inspector.get_foreign_keys("doctor_profiles")
            if fk.get("name")
        }
        if "fk_doctor_profiles_shift_id_shifts" in fk_names:
            op.drop_constraint(
                "fk_doctor_profiles_shift_id_shifts",
                "doctor_profiles",
                type_="foreignkey",
            )
        idx_names = {idx["name"] for idx in inspector.get_indexes("doctor_profiles")}
        if "ix_doctor_profiles_shift_id" in idx_names:
            op.drop_index("ix_doctor_profiles_shift_id", table_name="doctor_profiles")
        op.drop_column("doctor_profiles", "shift_id")
        doctor_cols.discard("shift_id")

    if "shifts" in inspector.get_table_names():
        shift_indexes = {idx["name"] for idx in inspector.get_indexes("shifts")}
        if "ix_shifts_id" in shift_indexes:
            op.drop_index("ix_shifts_id", table_name="shifts")
        op.drop_table("shifts")

    if "employee_id" not in doctor_cols:
        op.add_column(
            "doctor_profiles",
            sa.Column("employee_id", sa.String(length=50), nullable=True),
        )
        op.create_index(
            op.f("ix_doctor_profiles_employee_id"),
            "doctor_profiles",
            ["employee_id"],
            unique=True,
        )
    if "joining_date" not in doctor_cols:
        op.add_column(
            "doctor_profiles",
            sa.Column("joining_date", sa.Date(), nullable=True),
        )
    if "shift_name" not in doctor_cols:
        op.add_column(
            "doctor_profiles",
            sa.Column("shift_name", sa.String(length=100), nullable=True),
        )
    if "shift_start_time" not in doctor_cols:
        op.add_column(
            "doctor_profiles",
            sa.Column("shift_start_time", sa.String(length=10), nullable=True),
        )
    if "shift_end_time" not in doctor_cols:
        op.add_column(
            "doctor_profiles",
            sa.Column("shift_end_time", sa.String(length=10), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    doctor_cols = {c["name"] for c in inspector.get_columns("doctor_profiles")}

    for col in ("shift_end_time", "shift_start_time", "shift_name", "joining_date"):
        if col in doctor_cols:
            op.drop_column("doctor_profiles", col)

    if "employee_id" in doctor_cols:
        op.drop_index(
            op.f("ix_doctor_profiles_employee_id"),
            table_name="doctor_profiles",
        )
        op.drop_column("doctor_profiles", "employee_id")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "emergency_contact_name" in user_cols:
        op.drop_column("users", "emergency_contact_name")
