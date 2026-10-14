"""appointment status enum, doctor_queue_next_requests table, queue_id FK

Revision ID: e1f2a3b4c5d6
Revises: 7954ceb7aea4
Create Date: 2026-06-23 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "7954ceb7aea4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_names(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE appointmentstatus AS ENUM (
                'scheduled', 'waiting', 'in_progress', 'completed', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    if _table_exists(inspector, "appointments"):
        cols = _column_names(inspector, "appointments")
        if "status" in cols:
            status_col = next(c for c in inspector.get_columns("appointments") if c["name"] == "status")
            type_name = str(status_col["type"]).upper()
            if "APPOINTMENTSTATUS" not in type_name:
                op.execute(
                    "UPDATE appointments SET status = 'scheduled' "
                    "WHERE status IS NULL OR TRIM(status) = ''"
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
                op.execute(
                    "ALTER TABLE appointments ALTER COLUMN status SET NOT NULL"
                )

    if not _table_exists(inspector, "doctor_queue_next_requests"):
        op.create_table(
            "doctor_queue_next_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=False),
            sa.Column("appointment_id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("queue_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("request_date", sa.Date(), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("handled_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["queue_id"], ["patient_queue.id"]),
            sa.ForeignKeyConstraint(["handled_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_doctor_queue_next_requests_doctor_id",
            "doctor_queue_next_requests",
            ["doctor_id"],
        )
        op.create_index(
            "ix_doctor_queue_next_requests_appointment_id",
            "doctor_queue_next_requests",
            ["appointment_id"],
        )
        op.create_index(
            "ix_doctor_queue_next_requests_request_date",
            "doctor_queue_next_requests",
            ["request_date"],
        )
        op.create_index(
            "ix_doctor_queue_next_requests_queue_id",
            "doctor_queue_next_requests",
            ["queue_id"],
        )
    else:
        cols = _column_names(inspector, "doctor_queue_next_requests")
        if "queue_id" not in cols:
            op.add_column(
                "doctor_queue_next_requests",
                sa.Column("queue_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_doctor_queue_next_requests_queue_id",
                "doctor_queue_next_requests",
                "patient_queue",
                ["queue_id"],
                ["id"],
            )
            op.create_index(
                "ix_doctor_queue_next_requests_queue_id",
                "doctor_queue_next_requests",
                ["queue_id"],
            )

        op.execute(
            """
            UPDATE doctor_queue_next_requests AS d
            SET queue_id = pq.id
            FROM patient_queue AS pq
            WHERE d.queue_id IS NULL
              AND pq.appointment_id = d.appointment_id
              AND pq.queue_date = d.request_date
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, "doctor_queue_next_requests"):
        cols = _column_names(inspector, "doctor_queue_next_requests")
        if "queue_id" in cols:
            op.drop_index(
                "ix_doctor_queue_next_requests_queue_id",
                table_name="doctor_queue_next_requests",
            )
            op.drop_constraint(
                "fk_doctor_queue_next_requests_queue_id",
                "doctor_queue_next_requests",
                type_="foreignkey",
            )
            op.drop_column("doctor_queue_next_requests", "queue_id")

    if _table_exists(inspector, "appointments"):
        cols = _column_names(inspector, "appointments")
        if "status" in cols:
            status_col = next(c for c in inspector.get_columns("appointments") if c["name"] == "status")
            type_name = str(status_col["type"]).upper()
            if "APPOINTMENTSTATUS" in type_name:
                op.execute(
                    """
                    ALTER TABLE appointments
                    ALTER COLUMN status TYPE VARCHAR
                    USING status::text
                    """
                )
                op.execute(
                    "ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT"
                )
                op.execute(
                    "ALTER TABLE appointments ALTER COLUMN status DROP NOT NULL"
                )

    op.execute("DROP TYPE IF EXISTS appointmentstatus")
