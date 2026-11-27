"""Link a patient row to the login user.

Revision ID: i3j4k5l6m7n8
Revises: b8d2f0c3e5a7, h2i3j4k5l6m7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, Sequence[str], None] = ("b8d2f0c3e5a7", "h2i3j4k5l6m7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("patients")}
    if "user_id" not in columns:
        op.add_column("patients", sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index("ix_patients_user_id", "patients", ["user_id"], unique=True)
        op.create_foreign_key("fk_patients_user_id", "patients", "users", ["user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_patients_user_id", "patients", type_="foreignkey")
    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_column("patients", "user_id")
