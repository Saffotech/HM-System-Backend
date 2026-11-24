"""Copy global role permissions into a per-hospital grant table.

Revision ID: h2i3j4k5l6m7
Revises: 282ce03aff1f, c2d3e4f5g6h7, laborder20260825, n4o5p6q7r8s9, o8p9q0r1s2t3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = (
    "282ce03aff1f",
    "c2d3e4f5g6h7",
    "laborder20260825",
    "n4o5p6q7r8s9",
    "o8p9q0r1s2t3",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # create_all may already have created these tables before Alembic records
    # this revision. Still create them on a database that does not have them,
    # and still add the index and the one-time template copy.
    if "tenant_role_permission_state" not in tables:
        op.create_table(
            "tenant_role_permission_state",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
            sa.PrimaryKeyConstraint("tenant_id", "role_id"),
        )
    permissions_created = "tenant_role_permissions" not in tables
    if permissions_created:
        op.create_table(
            "tenant_role_permissions",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
            sa.PrimaryKeyConstraint("tenant_id", "role_id", "permission_id"),
        )

    index_names = set()
    if not permissions_created:
        index_names = {
            index["name"]
            for index in inspector.get_indexes("tenant_role_permissions")
        }
    if "ix_tenant_role_permissions_role" not in index_names:
        op.create_index(
            "ix_tenant_role_permissions_role",
            "tenant_role_permissions",
            ["tenant_id", "role_id"],
        )

    # Copy the global template only where a hospital does not already have a
    # state row. Permissions are inserted first so the new state rows do not
    # hide hospitals that still need the template. Existing grants stay as they are.
    op.execute(
        """
        INSERT INTO tenant_role_permissions (tenant_id, role_id, permission_id)
        SELECT t.id, rp.role_id, rp.permission_id
        FROM tenants t
        JOIN role_permissions rp ON true
        WHERE NOT EXISTS (
            SELECT 1
            FROM tenant_role_permission_state existing
            WHERE existing.tenant_id = t.id
              AND existing.role_id = rp.role_id
        )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO tenant_role_permission_state (tenant_id, role_id)
        SELECT t.id, r.id
        FROM tenants t
        CROSS JOIN roles r
        WHERE NOT EXISTS (
            SELECT 1
            FROM tenant_role_permission_state existing
            WHERE existing.tenant_id = t.id
              AND existing.role_id = r.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_role_permissions_role", table_name="tenant_role_permissions")
    op.drop_table("tenant_role_permissions")
    op.drop_table("tenant_role_permission_state")
