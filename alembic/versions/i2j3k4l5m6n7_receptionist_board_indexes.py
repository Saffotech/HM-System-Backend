"""Receptionist board indexes (queue join + appointment day filters).

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-08-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, Sequence[str], None] = "h1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    queue_indexes = _index_names(inspector, "patient_queue")
    if "ix_patient_queue_appointment_id_queue_date" not in queue_indexes:
        op.create_index(
            "ix_patient_queue_appointment_id_queue_date",
            "patient_queue",
            ["appointment_id", "queue_date"],
        )

    apt_indexes = _index_names(inspector, "appointments")
    if "ix_appointments_doctor_id_scheduled_at" not in apt_indexes:
        op.create_index(
            "ix_appointments_doctor_id_scheduled_at",
            "appointments",
            ["doctor_id", "scheduled_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    apt_indexes = _index_names(inspector, "appointments")
    if "ix_appointments_doctor_id_scheduled_at" in apt_indexes:
        op.drop_index(
            "ix_appointments_doctor_id_scheduled_at", table_name="appointments"
        )

    queue_indexes = _index_names(inspector, "patient_queue")
    if "ix_patient_queue_appointment_id_queue_date" in queue_indexes:
        op.drop_index(
            "ix_patient_queue_appointment_id_queue_date",
            table_name="patient_queue",
        )
