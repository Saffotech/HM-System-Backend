"""Hospital live schema baseline (do not replay historical chain).

Revision ID: c9d0e1f2a3b4
Revises: 91445aa645ea
Create Date: 2026-08-24

Marks the existing `Hospital` database as Alembic-current for this app.

This database was created/updated via SQLAlchemy create_all plus targeted
SQL (not `alembic upgrade` from an empty alembic_version). Historical
revision files are kept on disk unchanged.

Intentionally NOT executed on this database (leftover objects remain):
- w1x2y3z4a5b6 — drop emergency_alerts
- r6s7t8u9v0w1 — drop doctor_schedules / doctor_leaves / doctor_queue_next_requests
- h1i2j3k4l5m6 — OPD payment ledger rewrite
- e8f9a0b1c2d3 unique active-bed cleanup (assigned_until already present)
- t8u9v0w1x2y3 / u9v0w1x2y3z4 — labteststatus enum rebuild

Already present on this database (applied out-of-band, matching upgrade()):
- a2b3c4d5e6f7 patients.registration_source
- g0a1b2c3d4e5 / i2j3k4l5m6n7 dashboard/board indexes
- b3c4d5e6f7a8 IPD notification enum values
- d5e6f7a8b9c0 audit_logs.user_agent
- v0w1x2y3z4a5 lab_test_orders.department_id
- c4d5e6f7a8b9 lab/prescription admission_id parent
- s7t8u9v0w1x2 prescription_items.duration VARCHAR(50)

upgrade()/downgrade() are no-ops. Do not `alembic upgrade head` from an
empty version table (that replays a1b2c3d4e5f6 create_table).
"""
from typing import Sequence, Union

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "91445aa645ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
