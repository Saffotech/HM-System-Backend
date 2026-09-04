"""Create ipd_admission_care_team for associated doctors.

Revision ID: r1s2t3u4v5w6
Revises: q0r1s2t3u4v5
Create Date: 2026-09-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, Sequence[str], None] = "q0r1s2t3u4v5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ipd_admission_care_team" in inspector.get_table_names():
        return
    op.create_table(
        "ipd_admission_care_team",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "admission_id",
            sa.Integer(),
            sa.ForeignKey("ipd_admissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id"),
            nullable=True,
        ),
        sa.Column(
            "added_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "admission_id",
            "doctor_id",
            name="uq_ipd_admission_care_team_admission_doctor",
        ),
    )
    op.create_index(
        "ix_ipd_admission_care_team_admission_id",
        "ipd_admission_care_team",
        ["admission_id"],
    )
    op.create_index(
        "ix_ipd_admission_care_team_doctor_id",
        "ipd_admission_care_team",
        ["doctor_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ipd_admission_care_team" not in inspector.get_table_names():
        return
    op.drop_index(
        "ix_ipd_admission_care_team_doctor_id",
        table_name="ipd_admission_care_team",
    )
    op.drop_index(
        "ix_ipd_admission_care_team_admission_id",
        table_name="ipd_admission_care_team",
    )
    op.drop_table("ipd_admission_care_team")
