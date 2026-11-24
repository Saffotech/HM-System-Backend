"""appointment clinical fields (diagnosis, follow_up_date)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("appointments")}
    if "diagnosis" not in columns:
        op.add_column("appointments", sa.Column("diagnosis", sa.Text(), nullable=True))
    if "follow_up_date" not in columns:
        op.add_column("appointments", sa.Column("follow_up_date", sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("appointments")}
    if "follow_up_date" in columns:
        op.drop_column("appointments", "follow_up_date")
    if "diagnosis" in columns:
        op.drop_column("appointments", "diagnosis")
