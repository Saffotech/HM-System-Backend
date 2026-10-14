"""IPD insurance claims + admission payment_type.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, Sequence[str], None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ipd_admissions" in inspector.get_table_names():
        cols = _columns(inspector, "ipd_admissions")
        if "payment_type" not in cols:
            op.add_column(
                "ipd_admissions",
                sa.Column(
                    "payment_type",
                    sa.String(),
                    nullable=False,
                    server_default="self",
                ),
            )
            op.alter_column("ipd_admissions", "payment_type", server_default=None)
            op.create_index(
                "ix_ipd_admissions_payment_type",
                "ipd_admissions",
                ["payment_type"],
            )
        if "self_pay_method" not in cols:
            op.add_column(
                "ipd_admissions",
                sa.Column("self_pay_method", sa.String(), nullable=True),
            )

    if "ipd_insurance_claims" not in inspector.get_table_names():
        op.create_table(
            "ipd_insurance_claims",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admission_id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("claim_type", sa.String(), nullable=False),
            sa.Column("insurer", sa.String(), nullable=False),
            sa.Column("policy_no", sa.String(), nullable=False),
            sa.Column("policy_holder", sa.String(), nullable=False),
            sa.Column("relationship", sa.String(), nullable=False),
            sa.Column("member_id", sa.String(), nullable=True),
            sa.Column("claimed_amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("estimate_amount", sa.Float(), nullable=True),
            sa.Column("approved_amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("available_si", sa.Float(), nullable=True),
            sa.Column(
                "policy_status",
                sa.String(),
                nullable=False,
                server_default="Active",
            ),
            sa.Column(
                "claim_status",
                sa.String(),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "insurance_payments",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "patient_payments",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["admission_id"],
                ["ipd_admissions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.UniqueConstraint("admission_id", name="uq_ipd_insurance_claims_admission_id"),
        )
        op.create_index("ix_ipd_insurance_claims_id", "ipd_insurance_claims", ["id"])
        op.create_index(
            "ix_ipd_insurance_claims_admission_id",
            "ipd_insurance_claims",
            ["admission_id"],
            unique=True,
        )
        op.create_index(
            "ix_ipd_insurance_claims_patient_id",
            "ipd_insurance_claims",
            ["patient_id"],
        )
        op.create_index(
            "ix_ipd_insurance_claims_claim_type",
            "ipd_insurance_claims",
            ["claim_type"],
        )
        op.create_index(
            "ix_ipd_insurance_claims_policy_no",
            "ipd_insurance_claims",
            ["policy_no"],
        )
        op.create_index(
            "ix_ipd_insurance_claims_claim_status",
            "ipd_insurance_claims",
            ["claim_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ipd_insurance_claims" in inspector.get_table_names():
        op.drop_table("ipd_insurance_claims")

    if "ipd_admissions" in inspector.get_table_names():
        cols = _columns(inspector, "ipd_admissions")
        if "self_pay_method" in cols:
            op.drop_column("ipd_admissions", "self_pay_method")
        if "payment_type" in cols:
            op.drop_index("ix_ipd_admissions_payment_type", table_name="ipd_admissions")
            op.drop_column("ipd_admissions", "payment_type")
