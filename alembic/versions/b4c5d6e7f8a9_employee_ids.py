"""Per-hospital employee numbers (EMP-0001) on staff profiles.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-11-03
"""
from typing import Sequence, Union
import re

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE_TABLES = {
    "doctor": "doctor_profiles",
    "nurse": "nurse_profiles",
    "receptionist": "receptionist_profiles",
    "lab_technician": "lab_technician_profiles",
    "opd_billing": "opd_billing_profiles",
    "ipd": "ipd_profiles",
    "pharmacist": "pharmacist_profiles",
    "admin": "admin_profiles",
    "manager": "manager_profiles",
}

_EMPLOYEE_NUMBER = re.compile(r"^EMP-(\d+)$", re.IGNORECASE)


def _drop_global_unique(bind) -> None:
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for table in _ROLE_TABLES.values():
        if table not in existing:
            continue
        for constraint in inspector.get_unique_constraints(table):
            columns = constraint.get("column_names") or []
            if columns == ["employee_id"] and constraint.get("name"):
                op.drop_constraint(constraint["name"], table, type_="unique")
        inspector = sa.inspect(bind)
        for index in inspector.get_indexes(table):
            columns = index.get("column_names") or []
            if index.get("unique") and columns == ["employee_id"] and index.get("name"):
                op.drop_index(index["name"], table_name=table)
        inspector = sa.inspect(bind)
        indexes = inspector.get_indexes(table)
        has_index = any((index.get("column_names") or []) == ["employee_id"] for index in indexes)
        if not has_index:
            op.create_index(f"ix_{table}_employee_id", table, ["employee_id"])


def _backfill(bind) -> None:
    existing = set(sa.inspect(bind).get_table_names())
    tables = [table for table in _ROLE_TABLES.values() if table in existing]
    tenant_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT DISTINCT tenant_id FROM users WHERE tenant_id IS NOT NULL")
        )
    ]
    for tenant_id in tenant_ids:
        highest = 0
        for table in tables:
            rows = bind.execute(
                sa.text(
                    f"""
                    SELECT p.employee_id
                    FROM {table} p
                    JOIN users u ON u.id = p.user_id
                    WHERE u.tenant_id = :tenant_id
                      AND p.employee_id IS NOT NULL
                    """
                ),
                {"tenant_id": tenant_id},
            )
            for (employee_id,) in rows:
                match = _EMPLOYEE_NUMBER.match(str(employee_id).strip())
                if match:
                    highest = max(highest, int(match.group(1)))

        staff = bind.execute(
            sa.text(
                """
                SELECT u.id, r.name
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.tenant_id = :tenant_id
                  AND u.deleted_at IS NULL
                ORDER BY u.id
                """
            ),
            {"tenant_id": tenant_id},
        ).fetchall()

        for user_id, role_name in staff:
            table = _ROLE_TABLES.get(role_name)
            if not table or table not in existing:
                continue
            current = bind.execute(
                sa.text(f"SELECT employee_id FROM {table} WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).fetchone()
            if current is None or (current[0] and str(current[0]).strip()):
                continue

            reused = None
            for other in tables:
                other_row = bind.execute(
                    sa.text(
                        f"""
                        SELECT employee_id
                        FROM {other}
                        WHERE user_id = :user_id
                          AND employee_id IS NOT NULL
                        """
                    ),
                    {"user_id": user_id},
                ).fetchone()
                if other_row and str(other_row[0]).strip():
                    reused = str(other_row[0]).strip()
                    break

            if reused:
                value = reused
            else:
                highest += 1
                value = f"EMP-{highest:04d}"

            bind.execute(
                sa.text(
                    f"UPDATE {table} SET employee_id = :employee_id WHERE user_id = :user_id"
                ),
                {"user_id": user_id, "employee_id": value},
            )

        if highest:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO tenant_employee_sequences (tenant_id, last_number)
                    VALUES (:tenant_id, :last_number)
                    ON CONFLICT (tenant_id)
                    DO UPDATE SET last_number = GREATEST(
                        tenant_employee_sequences.last_number,
                        EXCLUDED.last_number
                    )
                    """
                ),
                {"tenant_id": tenant_id, "last_number": highest},
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tenants" not in inspector.get_table_names():
        return
    if "tenant_employee_sequences" not in inspector.get_table_names():
        op.create_table(
            "tenant_employee_sequences",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("last_number", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("tenant_id"),
        )
    _drop_global_unique(bind)
    _backfill(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if "tenant_employee_sequences" in sa.inspect(bind).get_table_names():
        op.drop_table("tenant_employee_sequences")
