"""Simplify appointment/queue statuses: scheduled → completed/no_show/cancelled.

Revision ID: q5r6s7t8u9v0
Revises: p4q5r6s7t8u9
Create Date: 2026-07-14

PostgreSQL enums cannot accept new labels via SET until the type changes.
Convert status columns to VARCHAR first, remap values, then recreate enums.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q5r6s7t8u9v0"
down_revision: Union[str, Sequence[str], None] = "p4q5r6s7t8u9"
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
            # 1) Leave enum — 'scheduled' is not a valid label yet.
            op.execute("ALTER TABLE patient_queue ALTER COLUMN status DROP DEFAULT")
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )

            # 2) Remap old intermediate statuses (handle lower/upper variants).
            op.execute(
                """
                UPDATE patient_queue
                SET status = 'scheduled'
                WHERE lower(status) IN ('waiting', 'vitals_completed')
                """
            )
            op.execute("UPDATE patient_queue SET status = lower(status)")

            # 3) Recreate enum with final values.
            op.execute("DROP TYPE IF EXISTS queuestatus")
            op.execute(
                """
                CREATE TYPE queuestatus AS ENUM (
                    'scheduled',
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
            op.execute(
                "ALTER TABLE patient_queue ALTER COLUMN status SET DEFAULT 'scheduled'"
            )

        if _table_exists(inspector, "appointments"):
            op.execute("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT")
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute(
                """
                UPDATE appointments
                SET status = 'scheduled'
                WHERE lower(status) = 'waiting'
                """
            )
            op.execute("UPDATE appointments SET status = lower(status)")

            op.execute("DROP TYPE IF EXISTS appointmentstatus")
            op.execute(
                """
                CREATE TYPE appointmentstatus AS ENUM (
                    'scheduled',
                    'completed',
                    'cancelled',
                    'no_show'
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
                SET status = 'scheduled'
                WHERE lower(status) IN ('waiting', 'vitals_completed')
                """
            )
        if _table_exists(inspector, "appointments"):
            op.execute(
                """
                UPDATE appointments
                SET status = 'scheduled'
                WHERE lower(status) = 'waiting'
                """
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if dialect == "postgresql":
        if _table_exists(inspector, "patient_queue"):
            op.execute("ALTER TABLE patient_queue ALTER COLUMN status DROP DEFAULT")
            op.execute(
                """
                ALTER TABLE patient_queue
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute(
                """
                UPDATE patient_queue
                SET status = 'waiting'
                WHERE lower(status) = 'scheduled'
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
            op.execute(
                "ALTER TABLE patient_queue ALTER COLUMN status SET DEFAULT 'waiting'"
            )

        if _table_exists(inspector, "appointments"):
            op.execute("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT")
            op.execute(
                """
                ALTER TABLE appointments
                ALTER COLUMN status TYPE VARCHAR
                USING status::text
                """
            )
            op.execute(
                """
                UPDATE appointments
                SET status = 'scheduled'
                WHERE lower(status) = 'no_show'
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
                WHERE status = 'scheduled'
                """
            )
        if _table_exists(inspector, "appointments"):
            op.execute(
                """
                UPDATE appointments
                SET status = 'scheduled'
                WHERE status = 'no_show'
                """
            )
