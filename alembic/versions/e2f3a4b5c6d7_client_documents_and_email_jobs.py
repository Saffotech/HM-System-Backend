"""Client document master, requests, and email jobs.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6

Fresh databases may already have these tables from metadata create_all.
This revision creates them only when missing and adds legal document columns.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "document_types" not in _tables():
        op.create_table(
            "document_types",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("requirement_type", sa.String(30), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("allowed_file_types", sa.String(200), nullable=False),
            sa.Column("max_file_size_mb", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("linked_checklist_code", sa.String(80)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")),
            sa.UniqueConstraint("code", name="uq_document_types_code"),
        )
    if "document_upload_requests" not in _tables():
        op.create_table(
            "document_upload_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("legal_cases.id"), nullable=False),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("request_type", sa.String(30), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("recipient_email", sa.String(200), nullable=False),
            sa.Column("recipient_name", sa.String(200)),
            sa.Column("recipient_source", sa.String(40), nullable=False),
            sa.Column("hospital_name_snapshot", sa.String(200), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("token_hash", name="uq_document_upload_requests_token"),
        )
    if "document_upload_request_items" not in _tables():
        op.create_table(
            "document_upload_request_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("document_upload_requests.id"), nullable=False),
            sa.Column("document_type_id", sa.Integer(), sa.ForeignKey("document_types.id")),
            sa.Column("document_code", sa.String(80), nullable=False),
            sa.Column("document_name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("requirement_type", sa.String(30), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False),
            sa.Column("allowed_file_types", sa.String(200), nullable=False),
            sa.Column("max_file_size_mb", sa.Integer(), nullable=False),
            sa.Column("display_order", sa.Integer(), nullable=False),
            sa.Column("review_remarks", sa.Text()),
            sa.Column("replacement_document_id", sa.Integer(), sa.ForeignKey("legal_documents.id")),
        )
    if "temporary_document_uploads" not in _tables():
        op.create_table(
            "temporary_document_uploads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("document_upload_requests.id"), nullable=False),
            sa.Column("request_item_id", sa.Integer(), sa.ForeignKey("document_upload_request_items.id"), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_path", sa.String(500), nullable=False),
            sa.Column("mime_type", sa.String(120), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("request_id", "request_item_id", name="uq_temp_upload_request_item"),
        )
    if "email_jobs" not in _tables():
        op.create_table(
            "email_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_type", sa.String(60), nullable=False),
            sa.Column("case_id", sa.Integer()),
            sa.Column("document_request_id", sa.Integer()),
            sa.Column("recipient_email", sa.String(200), nullable=False),
            sa.Column("recipient_name", sa.String(200)),
            sa.Column("subject", sa.String(300), nullable=False),
            sa.Column("template_name", sa.String(80), nullable=False),
            sa.Column("encrypted_payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("next_retry_at", sa.DateTime(timezone=True)),
            sa.Column("provider_reference", sa.String(200)),
            sa.Column("sanitized_error", sa.String(500)),
            sa.Column("idempotency_key", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processing_started_at", sa.DateTime(timezone=True)),
            sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True)),
            sa.Column("processing_owner", sa.String(80)),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
            sa.Column("failed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("idempotency_key", name="uq_email_jobs_idempotency"),
        )
    if "document_review_history" not in _tables():
        op.create_table(
            "document_review_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("legal_documents.id"), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("previous_status", sa.String(40)),
            sa.Column("new_status", sa.String(40), nullable=False),
            sa.Column("remarks", sa.Text()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    additions = (
        ("document_type_id", sa.Integer()),
        ("mime_type", sa.String(120)),
        ("file_size_bytes", sa.Integer()),
        ("upload_source", sa.String(20)),
        ("upload_request_id", sa.Integer()),
        ("review_remarks", sa.Text()),
        ("version", sa.Integer()),
        ("replaces_document_id", sa.Integer()),
        ("is_current", sa.Boolean()),
    )
    existing = _columns("legal_documents")
    for name, column in additions:
        if name not in existing and "legal_documents" in _tables():
            op.add_column("legal_documents", sa.Column(name, column, nullable=True))
    if "legal_checklist_items" in _tables() and "document_type_id" not in _columns("legal_checklist_items"):
        op.add_column("legal_checklist_items", sa.Column("document_type_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade of e2f3a4b5c6d7 is not supported because it would drop document history. "
        "Restore the database from backup and stamp the previous revision only after the schema matches that backup."
    )
