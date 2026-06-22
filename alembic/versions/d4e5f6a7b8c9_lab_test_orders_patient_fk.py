"""lab_test_orders patient_id foreign key

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "4de691ce7fd6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("lab_test_orders")
    }
    if "fk_lab_test_orders_patient_id" not in fks:
        op.create_foreign_key(
            "fk_lab_test_orders_patient_id",
            "lab_test_orders",
            "patients",
            ["patient_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("lab_test_orders")
    }
    if "fk_lab_test_orders_patient_id" in fks:
        op.drop_constraint(
            "fk_lab_test_orders_patient_id",
            "lab_test_orders",
            type_="foreignkey",
        )
