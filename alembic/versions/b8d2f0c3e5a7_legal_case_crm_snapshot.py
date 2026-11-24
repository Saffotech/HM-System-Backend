"""Store the CRM agreement snapshot on the legal case.

Revision ID: b8d2f0c3e5a7
Revises: 282ce03aff1f
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2f0c3e5a7"
down_revision: Union[str, Sequence[str], None] = "282ce03aff1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("hospital_type", sa.String(50)),
    ("state", sa.String(100)),
    ("hospital_email", sa.String(200)),
    ("contact_person", sa.String(200)),
    ("designation", sa.String(120)),
    ("contact_phone", sa.String(30)),
    ("contact_email", sa.String(200)),
    ("lead_source", sa.String(50)),
    ("priority", sa.String(20)),
    ("requirement", sa.Text()),
    ("assigned_employee_id", sa.Integer()),
    ("assigned_employee_name", sa.String(200)),
    ("agreed_at", sa.DateTime(timezone=True)),
    ("agreed_by_name", sa.String(200)),
    ("handover_note", sa.Text()),
    ("billing_cycle", sa.String(20)),
    ("commercial_change_note", sa.Text()),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "legal_cases" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("legal_cases")}
    for name, column_type in COLUMNS:
        if name in existing:
            continue
        op.add_column("legal_cases", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "legal_cases" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("legal_cases")}
    for name, _column_type in reversed(COLUMNS):
        if name in existing:
            op.drop_column("legal_cases", name)
