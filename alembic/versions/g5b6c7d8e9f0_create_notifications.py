"""create notifications table

Revision ID: g5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

notification_type_enum = sa.Enum(
    "NEW_APPOINTMENT",
    "APPOINTMENT_CANCELLED",
    "APPOINTMENT_RESCHEDULED",
    "PATIENT_CHECKED_IN",
    "LAB_REPORT_READY",
    "LAB_REPORT_UPDATED",
    "PRESCRIPTION_CREATED",
    "PRESCRIPTION_UPDATED",
    "EMERGENCY_ALERT",
    name="notificationtype",
)

source_module_enum = sa.Enum(
    "OPD_BILLING",
    "LAB",
    "RECEPTIONIST",
    "NURSE",
    "PHARMACY",
    "ADMIN",
    "SYSTEM",
    name="sourcemodule",
)

reference_type_enum = sa.Enum(
    "APPOINTMENT",
    "LAB_ORDER",
    "PRESCRIPTION",
    "BILL",
    "PATIENT",
    name="referencetype",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    notification_type_enum.create(bind, checkfirst=True)
    source_module_enum.create(bind, checkfirst=True)
    reference_type_enum.create(bind, checkfirst=True)

    if "notifications" not in inspector.get_table_names():
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("notification_type", notification_type_enum, nullable=False),
            sa.Column("source_module", source_module_enum, nullable=False),
            sa.Column("reference_type", reference_type_enum, nullable=False),
            sa.Column("reference_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_by_name", sa.String(length=255), nullable=True),
            sa.Column(
                "is_read",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
        op.create_index(
            op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False
        )
        op.create_index(
            op.f("ix_notifications_notification_type"),
            "notifications",
            ["notification_type"],
            unique=False,
        )
        op.create_index(
            op.f("ix_notifications_source_module"),
            "notifications",
            ["source_module"],
            unique=False,
        )
        op.create_index(
            op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False
        )
        op.create_index(
            op.f("ix_notifications_created_at"),
            "notifications",
            ["created_at"],
            unique=False,
        )
        op.create_index(
            "ix_notifications_user_created",
            "notifications",
            ["user_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_notifications_user_unread",
            "notifications",
            ["user_id", "is_read"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "notifications" in inspector.get_table_names():
        op.drop_index("ix_notifications_user_unread", table_name="notifications")
        op.drop_index("ix_notifications_user_created", table_name="notifications")
        op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_source_module"), table_name="notifications")
        op.drop_index(
            op.f("ix_notifications_notification_type"), table_name="notifications"
        )
        op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
        op.drop_table("notifications")

    reference_type_enum.drop(bind, checkfirst=True)
    source_module_enum.drop(bind, checkfirst=True)
    notification_type_enum.drop(bind, checkfirst=True)
