"""Drop orphan emergency_alerts table and related enums.

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-08-12

Nurse emergency alerts module was removed from the backend. The table and
Postgres enums are unused leftovers.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, Sequence[str], None] = "v0w1x2y3z4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _index_names(inspector, table: str) -> set[str]:
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, "emergency_alerts"):
        indexes = _index_names(inspector, "emergency_alerts")
        for ix in (
            "ix_emergency_alerts_alert_type",
            "ix_emergency_alerts_alert_uid",
            "ix_emergency_alerts_assigned_nurse_id",
            "ix_emergency_alerts_id",
            "ix_emergency_alerts_medication_administration_id",
            "ix_emergency_alerts_patient_id",
            "ix_emergency_alerts_severity",
            "ix_emergency_alerts_status",
            "ix_emergency_alerts_triggered_at",
            "ix_emergency_alerts_vital_id",
            "ix_emergency_alerts_ward_name",
        ):
            if ix in indexes:
                op.drop_index(ix, table_name="emergency_alerts")
        op.drop_table("emergency_alerts")

    # Enums may remain after table drop (Postgres).
    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS alertstatus")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE alerttype AS ENUM (
                'LOW_BP', 'HIGH_BP', 'HIGH_FEVER', 'CARDIAC',
                'LOW_SPO2', 'OVERDUE_MEDICATION', 'MANUAL', 'OTHER'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE alertseverity AS ENUM ('MEDIUM', 'HIGH', 'CRITICAL');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE alertstatus AS ENUM ('ACTIVE', 'RESOLVED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    if _table_exists(inspector, "emergency_alerts"):
        return

    op.create_table(
        "emergency_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("alert_uid", sa.String(50), nullable=False, unique=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column(
            "alert_type",
            sa.Enum(
                "LOW_BP",
                "HIGH_BP",
                "HIGH_FEVER",
                "CARDIAC",
                "LOW_SPO2",
                "OVERDUE_MEDICATION",
                "MANUAL",
                "OTHER",
                name="alerttype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="alertseverity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ward_name", sa.String(100), nullable=True),
        sa.Column("bed_number", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "RESOLVED", name="alertstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_nurse_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "escalated_to_doctor_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("escalation_notes", sa.Text(), nullable=True),
        sa.Column("vital_id", sa.Integer(), sa.ForeignKey("patient_vitals.id"), nullable=True),
        sa.Column(
            "medication_administration_id",
            sa.Integer(),
            sa.ForeignKey("medication_administrations.id"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_emergency_alerts_alert_uid", "emergency_alerts", ["alert_uid"])
    op.create_index("ix_emergency_alerts_patient_id", "emergency_alerts", ["patient_id"])
    op.create_index("ix_emergency_alerts_alert_type", "emergency_alerts", ["alert_type"])
    op.create_index("ix_emergency_alerts_severity", "emergency_alerts", ["severity"])
    op.create_index("ix_emergency_alerts_status", "emergency_alerts", ["status"])
    op.create_index("ix_emergency_alerts_ward_name", "emergency_alerts", ["ward_name"])
    op.create_index("ix_emergency_alerts_triggered_at", "emergency_alerts", ["triggered_at"])
    op.create_index(
        "ix_emergency_alerts_assigned_nurse_id",
        "emergency_alerts",
        ["assigned_nurse_id"],
    )
    op.create_index("ix_emergency_alerts_vital_id", "emergency_alerts", ["vital_id"])
    op.create_index(
        "ix_emergency_alerts_medication_administration_id",
        "emergency_alerts",
        ["medication_administration_id"],
    )
