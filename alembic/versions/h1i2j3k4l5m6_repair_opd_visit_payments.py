"""Cap OPD payment transactions and visit paid_amount to grand_total.

Revision ID: h1i2j3k4l5m6
Revises: g0a1b2c3d4e5
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "g0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from Services.opd_helpers import repair_visit_payment_ledger

    bind = op.get_bind()
    with Session(bind=bind) as db:
        repair_visit_payment_ledger(db)
        db.commit()


def downgrade() -> None:
    pass
