"""queue called status and called_by on patient_queue

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2026-06-23 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("patient_queue")}
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("patient_queue")}

    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE queuestatus ADD VALUE 'called';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    if "called_by" not in columns:
        op.add_column(
            "patient_queue",
            sa.Column("called_by", sa.Integer(), nullable=True),
        )
    if "fk_patient_queue_called_by_users" not in fk_names:
        op.create_foreign_key(
            "fk_patient_queue_called_by_users",
            "patient_queue",
            "users",
            ["called_by"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_patient_queue_called_by_users", "patient_queue", type_="foreignkey"
    )
    op.drop_column("patient_queue", "called_by")
