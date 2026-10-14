"""Allow null appointment_id on patient_vitals and nursing_notes for IPD.

Revision ID: j8d9e0f1a2b3
Revises: i7c8d9e0f1a2
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "j8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "i7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("patient_vitals", "appointment_id", nullable=True)
    op.alter_column("nursing_notes", "appointment_id", nullable=True)


def downgrade() -> None:
    op.alter_column("nursing_notes", "appointment_id", nullable=False)
    op.alter_column("patient_vitals", "appointment_id", nullable=False)
