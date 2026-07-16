"""Rename emergency_alerts:* permissions to nurse_alerts:*."""

from alembic import op
import sqlalchemy as sa

revision = "u9v0w1x2y3z4"
down_revision = "t8u9v0w1x2y3"
branch_labels = None
depends_on = None

RENAMES = [
    ("emergency_alerts:view", "nurse_alerts:view"),
    ("emergency_alerts:create", "nurse_alerts:create"),
    ("emergency_alerts:update", "nurse_alerts:update"),
    ("emergency_alerts:escalate", "nurse_alerts:escalate"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in RENAMES:
        conn.execute(
            sa.text("UPDATE permissions SET name = :new WHERE name = :old"),
            {"old": old, "new": new},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for old, new in RENAMES:
        conn.execute(
            sa.text("UPDATE permissions SET name = :old WHERE name = :new"),
            {"old": old, "new": new},
        )
