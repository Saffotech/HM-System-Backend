"""IPD doctor visits: nurse link, void flag, scale indexes.

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-08-24

- nurse_visit_id links billable IPD visit to nurse log (1:1)
- is_voided soft-cancels billing when nurse voids the visit
- Indexes support day-wise visit_number / billing queries at scale
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, Sequence[str], None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ipd_doctor_visits" in inspector.get_table_names():
        cols = _columns(inspector, "ipd_doctor_visits")
        idxs = _indexes(inspector, "ipd_doctor_visits")

        if "nurse_visit_id" not in cols:
            op.add_column(
                "ipd_doctor_visits",
                sa.Column("nurse_visit_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_ipd_doctor_visits_nurse_visit_id",
                "ipd_doctor_visits",
                "nurse_doctor_visits",
                ["nurse_visit_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index(
                "ix_ipd_doctor_visits_nurse_visit_id",
                "ipd_doctor_visits",
                ["nurse_visit_id"],
                unique=True,
            )

        if "is_voided" not in cols:
            op.add_column(
                "ipd_doctor_visits",
                sa.Column(
                    "is_voided",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )
            op.alter_column("ipd_doctor_visits", "is_voided", server_default=None)
            op.create_index(
                "ix_ipd_doctor_visits_is_voided",
                "ipd_doctor_visits",
                ["is_voided"],
            )

        if "ix_ipd_doctor_visits_admission_visited" not in idxs:
            op.create_index(
                "ix_ipd_doctor_visits_admission_visited",
                "ipd_doctor_visits",
                ["admission_id", "visited_at"],
            )
        if "ix_ipd_doctor_visits_admission_doctor_visited" not in idxs:
            op.create_index(
                "ix_ipd_doctor_visits_admission_doctor_visited",
                "ipd_doctor_visits",
                ["admission_id", "doctor_id", "visited_at"],
            )

    if "nurse_doctor_visits" in inspector.get_table_names():
        idxs = _indexes(inspector, "nurse_doctor_visits")
        if "ix_nurse_doctor_visits_patient_visited" not in idxs:
            op.create_index(
                "ix_nurse_doctor_visits_patient_visited",
                "nurse_doctor_visits",
                ["patient_id", "visited_at"],
            )
        if "ix_nurse_doctor_visits_patient_voided_visited" not in idxs:
            op.create_index(
                "ix_nurse_doctor_visits_patient_voided_visited",
                "nurse_doctor_visits",
                ["patient_id", "is_voided", "visited_at"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "nurse_doctor_visits" in inspector.get_table_names():
        idxs = _indexes(inspector, "nurse_doctor_visits")
        if "ix_nurse_doctor_visits_patient_voided_visited" in idxs:
            op.drop_index(
                "ix_nurse_doctor_visits_patient_voided_visited",
                table_name="nurse_doctor_visits",
            )
        if "ix_nurse_doctor_visits_patient_visited" in idxs:
            op.drop_index(
                "ix_nurse_doctor_visits_patient_visited",
                table_name="nurse_doctor_visits",
            )

    if "ipd_doctor_visits" in inspector.get_table_names():
        idxs = _indexes(inspector, "ipd_doctor_visits")
        cols = _columns(inspector, "ipd_doctor_visits")

        if "ix_ipd_doctor_visits_admission_doctor_visited" in idxs:
            op.drop_index(
                "ix_ipd_doctor_visits_admission_doctor_visited",
                table_name="ipd_doctor_visits",
            )
        if "ix_ipd_doctor_visits_admission_visited" in idxs:
            op.drop_index(
                "ix_ipd_doctor_visits_admission_visited",
                table_name="ipd_doctor_visits",
            )
        if "ix_ipd_doctor_visits_is_voided" in idxs:
            op.drop_index("ix_ipd_doctor_visits_is_voided", table_name="ipd_doctor_visits")
        if "ix_ipd_doctor_visits_nurse_visit_id" in idxs:
            op.drop_index(
                "ix_ipd_doctor_visits_nurse_visit_id",
                table_name="ipd_doctor_visits",
            )
        if "nurse_visit_id" in cols:
            op.drop_constraint(
                "fk_ipd_doctor_visits_nurse_visit_id",
                "ipd_doctor_visits",
                type_="foreignkey",
            )
            op.drop_column("ipd_doctor_visits", "nurse_visit_id")
        if "is_voided" in cols:
            op.drop_column("ipd_doctor_visits", "is_voided")
