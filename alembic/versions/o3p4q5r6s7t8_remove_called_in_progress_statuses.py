"""Remove called/in_progress queue and appointment statuses.

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-07-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o3p4q5r6s7t8"
down_revision: Union[str, Sequence[str], None] = "n2o3p4q5r6s7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if dialect == "postgresql":
        if _table_exists(inspector, "patient_queue"):
            op.execute(
                """
                UPDATE patient_queue
                SET status = 'waiting'
                WHERE status::text IN ('called', 'in_progress')
                """
            )
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute("DROP TYPE IF EXISTS queuestatus")
            op.execute(
                """
                CREATE TYPE queuestatus AS ENUM (
                    'waiting',
                    'vitals_completed',
                    'completed',
                    'cancelled',
                    'no_show'
                )
                """
            )
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE queuestatus
                USING status::queuestatus
                """
            )

        if _table_exists(inspector, "appointments"):
            op.execute(
                """
                UPDATE appointments
                SET status = 'waiting'
                WHERE status::text = 'in_progress'
                """
            )
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute("DROP TYPE IF EXISTS appointmentstatus")
            op.execute(
                """
                CREATE TYPE appointmentstatus AS ENUM (
                    'scheduled',
                    'waiting',
                    'completed',
                    'cancelled'
                )
                """
            )
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE appointmentstatus
                USING status::appointmentstatus
                """
            )
            op.execute(
                "ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'"
            )
    else:
        if _table_exists(inspector, "patient_queue"):
            op.execute(
                """
                UPDATE patient_queue
                SET status = 'waiting'
                WHERE status IN ('called', 'in_progress')
                """
            )
        if _table_exists(inspector, "appointments"):
            op.execute(
                """
                UPDATE appointments
                SET status = 'waiting'
                WHERE status = 'in_progress'
                """
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if dialect == "postgresql":
        if _table_exists(inspector, "patient_queue"):
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute("DROP TYPE IF EXISTS queuestatus")
            op.execute(
                """
                CREATE TYPE queuestatus AS ENUM (
                    'waiting',
                    'vitals_completed',
                    'called',
                    'in_progress',
                    'completed',
                    'cancelled',
                    'no_show'
                )
                """
            )
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE queuestatus
                USING status::queuestatus
                """
            )

        if _table_exists(inspector, "appointments"):
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute("DROP TYPE IF EXISTS appointmentstatus")
            op.execute(
                """
                CREATE TYPE appointmentstatus AS ENUM (
                    'scheduled',
                    'waiting',
                    'in_progress',
                    'completed',
                    'cancelled'
                )
                """
            )
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE appointmentstatus
                USING status::appointmentstatus
                """
            )
            op.execute(
                "ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'"
            )
