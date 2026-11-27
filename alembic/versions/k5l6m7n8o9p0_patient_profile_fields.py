"""Patient profile: emergency contact relation, and link desk-made logins.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, Sequence[str], None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("patients")}
    if "emergency_contact_relation" not in columns:
        op.add_column(
            "patients",
            sa.Column("emergency_contact_relation", sa.String(length=50), nullable=True),
        )

    # The desk already created a patient login (username = UHID) for every
    # registered patient. Link those logins to their patient row so the
    # patient app can find its own record.
    op.execute(
        """
        UPDATE patients AS p
        SET user_id = u.id
        FROM users AS u
        JOIN roles AS r ON r.id = u.role_id
        WHERE r.name = 'patient'
          AND u.username = p.patient_uid
          AND u.tenant_id = p.tenant_id
          AND p.user_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM patients AS other WHERE other.user_id = u.id)
        """
    )


def downgrade() -> None:
    op.drop_column("patients", "emergency_contact_relation")
