"""opd billing complete tables

Revision ID: a1b2c3d4e5f6
Revises: 35ae2eea2ec3
Create Date: 2026-05-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "35ae2eea2ec3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bill_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["visit_id"], ["opd_visits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bill_items_visit_id", "bill_items", ["visit_id"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_mode", sa.String(), nullable=False),
        sa.Column("transaction_reference", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["visit_id"], ["opd_visits.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_transactions_visit_id", "payment_transactions", ["visit_id"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("appointment_uid", sa.String(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("appointment_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_uid"),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])

    op.create_table(
        "beds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bed_number", sa.String(), nullable=False),
        sa.Column("ward_name", sa.String(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_beds_ward_name", "beds", ["ward_name"])

    op.create_index("ix_patients_phone", "patients", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_index("ix_beds_ward_name", table_name="beds")
    op.drop_table("beds")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_payment_transactions_visit_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_bill_items_visit_id", table_name="bill_items")
    op.drop_table("bill_items")
