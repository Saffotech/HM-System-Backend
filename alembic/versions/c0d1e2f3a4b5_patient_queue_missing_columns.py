"""patient_queue missing columns for doctor consult APIs

Revision ID: c0d1e2f3a4b5
Revises: b8e885b35927
Create Date: 2026-07-03 12:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b8e885b35927"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def _constraint_exists(inspector, name: str) -> bool:
    return any(c.get("name") == name for c in inspector.get_foreign_keys("patient_queue")) or name in {
        row[0]
        for row in op.get_bind().execute(
            sa.text("SELECT conname FROM pg_constraint WHERE conname = :n"),
            {"n": name},
        )
    }


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "patient_queue" not in inspector.get_table_names():
        return

    cols = _column_names(inspector, "patient_queue")

    if "appointment_uid" not in cols:
        op.add_column(
            "patient_queue",
            sa.Column("appointment_uid", sa.String(length=100), nullable=True),
        )
        op.create_index(
            "ix_patient_queue_appointment_uid",
            "patient_queue",
            ["appointment_uid"],
            unique=False,
        )

    if "created_by" not in cols:
        op.add_column("patient_queue", sa.Column("created_by", sa.Integer(), nullable=True))
    if "updated_by" not in cols:
        op.add_column("patient_queue", sa.Column("updated_by", sa.Integer(), nullable=True))
    if "updated_at" not in cols:
        op.add_column(
            "patient_queue",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )
    if "called_at" not in cols:
        op.add_column(
            "patient_queue",
            sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "called_by" not in cols:
        op.add_column("patient_queue", sa.Column("called_by", sa.Integer(), nullable=True))

    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE queuestatus ADD VALUE 'called';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE queuestatus ADD VALUE 'no_show';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    for fk_name, local_col in (
        ("fk_patient_queue_created_by", "created_by"),
        ("fk_patient_queue_updated_by", "updated_by"),
        ("fk_patient_queue_called_by_users", "called_by"),
    ):
        if not _constraint_exists(inspector, fk_name):
            op.create_foreign_key(fk_name, "patient_queue", "users", [local_col], ["id"])

    op.execute(
        """
        UPDATE patient_queue pq
        SET appointment_uid = a.appointment_uid
        FROM appointments a
        WHERE pq.appointment_id = a.id
          AND pq.appointment_uid IS NULL
        """
    )


def downgrade() -> None:
    pass
