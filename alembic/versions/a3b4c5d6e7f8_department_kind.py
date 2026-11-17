"""Store the department type chosen on the create form.

Revision ID: a3b4c5d6e7f8
Revises: 2210746371d0
Create Date: 2026-11-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "2210746371d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "departments" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("departments")}
    if "kind" not in columns:
        op.add_column(
            "departments",
            sa.Column("kind", sa.String(length=10), nullable=False, server_default="doctor"),
        )
        op.alter_column("departments", "kind", server_default=None)
    op.execute(
        """
        UPDATE departments
        SET kind = 'lab'
        WHERE upper(btrim(coalesce(code, ''))) IN ('LAB', 'LABORATORY', 'RAD', 'RADIOLOGY', 'IMAGING')
           OR (
                btrim(coalesce(code, '')) = ''
                AND upper(btrim(name)) IN ('LAB', 'LABORATORY', 'RAD', 'RADIOLOGY', 'IMAGING')
           )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "departments" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("departments")}
    if "kind" in columns:
        op.drop_column("departments", "kind")
