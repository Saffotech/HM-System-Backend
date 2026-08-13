"""Drop unused doctor_schedules, doctor_leaves, doctor_queue_next_requests.

Revision ID: r6s7t8u9v0w1
Revises: p5q6r7s8t9u0
Create Date: 2026-08-10

These tables supported unused doctor schedule/leave models and the old
doctor-request-next / receptionist send-in flow. Current app logic does not use them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r6s7t8u9v0w1"
down_revision: Union[str, Sequence[str], None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _index_names(inspector, table: str) -> set[str]:
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def _fk_names(inspector, table: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table) if fk.get("name")}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, "doctor_queue_next_requests"):
        fks = _fk_names(inspector, "doctor_queue_next_requests")
        indexes = _index_names(inspector, "doctor_queue_next_requests")
        if "fk_doctor_queue_next_requests_queue_id" in fks:
            op.drop_constraint(
                "fk_doctor_queue_next_requests_queue_id",
                "doctor_queue_next_requests",
                type_="foreignkey",
            )
        for ix in (
            "ix_doctor_queue_next_requests_queue_id",
            "ix_doctor_queue_next_requests_request_date",
            "ix_doctor_queue_next_requests_appointment_id",
            "ix_doctor_queue_next_requests_doctor_id",
        ):
            if ix in indexes:
                op.drop_index(ix, table_name="doctor_queue_next_requests")
        op.drop_table("doctor_queue_next_requests")

    if _table_exists(inspector, "doctor_leaves"):
        indexes = _index_names(inspector, "doctor_leaves")
        for ix in (
            "ix_doctor_leaves_end_date",
            "ix_doctor_leaves_start_date",
            "ix_doctor_leaves_doctor_id",
        ):
            if ix in indexes:
                op.drop_index(ix, table_name="doctor_leaves")
        op.drop_table("doctor_leaves")
        op.execute("DROP TYPE IF EXISTS doctorleavetype")

    if _table_exists(inspector, "doctor_schedules"):
        indexes = _index_names(inspector, "doctor_schedules")
        for ix in (
            "ix_doctor_schedules_day_of_week",
            "ix_doctor_schedules_doctor_id",
        ):
            if ix in indexes:
                op.drop_index(ix, table_name="doctor_schedules")
        op.drop_table("doctor_schedules")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "doctor_schedules"):
        op.create_table(
            "doctor_schedules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("shift_start", sa.Time(), nullable=False),
            sa.Column("shift_end", sa.Time(), nullable=False),
            sa.Column("consultation_duration_minutes", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])
        op.create_index("ix_doctor_schedules_day_of_week", "doctor_schedules", ["day_of_week"])

    if not _table_exists(inspector, "doctor_leaves"):
        op.create_table(
            "doctor_leaves",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("doctor_id", sa.Integer(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column(
                "leave_type",
                sa.Enum("leave", "holiday", name="doctorleavetype"),
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_doctor_leaves_doctor_id", "doctor_leaves", ["doctor_id"])
        op.create_index("ix_doctor_leaves_start_date", "doctor_leaves", ["start_date"])
        op.create_index("ix_doctor_leaves_end_date", "doctor_leaves", ["end_date"])

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
            sa.ForeignKeyConstraint(
                ["queue_id"],
                ["patient_queue.id"],
                name="fk_doctor_queue_next_requests_queue_id",
            ),
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
