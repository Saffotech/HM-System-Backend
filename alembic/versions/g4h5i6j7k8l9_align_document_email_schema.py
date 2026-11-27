"""Align document and email schema with the current models.

Revision ID: g4h5i6j7k8l9
Revises: f3a4b5c6d7e8

e2f3a4b5c6d7 created the new tables and columns, but left legal document
fields nullable and did not create the model indexes or document foreign keys.
This revision only adds missing objects and backfills existing rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g4h5i6j7k8l9"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = (
    ("ix_document_types_code", "document_types", "code"),
    ("ix_document_types_requirement_type", "document_types", "requirement_type"),
    ("ix_document_types_is_active", "document_types", "is_active"),
    ("ix_document_upload_requests_case_id", "document_upload_requests", "case_id"),
    ("ix_document_upload_requests_token_hash", "document_upload_requests", "token_hash"),
    ("ix_document_upload_requests_status", "document_upload_requests", "status"),
    ("ix_document_upload_request_items_request_id", "document_upload_request_items", "request_id"),
    ("ix_temporary_document_uploads_request_id", "temporary_document_uploads", "request_id"),
    ("ix_document_review_history_document_id", "document_review_history", "document_id"),
    ("ix_email_jobs_job_type", "email_jobs", "job_type"),
    ("ix_email_jobs_case_id", "email_jobs", "case_id"),
    ("ix_email_jobs_document_request_id", "email_jobs", "document_request_id"),
    ("ix_email_jobs_status", "email_jobs", "status"),
    ("ix_email_jobs_next_retry_at", "email_jobs", "next_retry_at"),
    ("ix_legal_documents_document_type_id", "legal_documents", "document_type_id"),
    ("ix_legal_documents_upload_request_id", "legal_documents", "upload_request_id"),
    ("ix_legal_checklist_items_document_type_id", "legal_checklist_items", "document_type_id"),
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_fk(table: str, column: str, referred: str) -> bool:
    inspector = _inspector()
    if table not in inspector.get_table_names():
        return True
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [column] and fk.get("referred_table") == referred:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "legal_documents" in tables:
        bind.execute(sa.text("UPDATE legal_documents SET upload_source = 'EMPLOYEE' WHERE upload_source IS NULL"))
        bind.execute(sa.text("UPDATE legal_documents SET version = 1 WHERE version IS NULL"))
        bind.execute(sa.text("UPDATE legal_documents SET is_current = TRUE WHERE is_current IS NULL"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN upload_source SET DEFAULT 'EMPLOYEE'"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN version SET DEFAULT 1"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN is_current SET DEFAULT TRUE"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN upload_source SET NOT NULL"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN version SET NOT NULL"))
        bind.execute(sa.text("ALTER TABLE legal_documents ALTER COLUMN is_current SET NOT NULL"))
        if not _has_fk("legal_documents", "document_type_id", "document_types"):
            op.create_foreign_key(
                "fk_legal_documents_document_type_id",
                "legal_documents",
                "document_types",
                ["document_type_id"],
                ["id"],
            )
        if not _has_fk("legal_documents", "replaces_document_id", "legal_documents"):
            op.create_foreign_key(
                "fk_legal_documents_replaces_document_id",
                "legal_documents",
                "legal_documents",
                ["replaces_document_id"],
                ["id"],
            )
    if "legal_checklist_items" in tables and not _has_fk(
        "legal_checklist_items", "document_type_id", "document_types"
    ):
        op.create_foreign_key(
            "fk_legal_checklist_items_document_type_id",
            "legal_checklist_items",
            "document_types",
            ["document_type_id"],
            ["id"],
        )
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    for name, table, column in INDEXES:
        if table not in tables:
            continue
        existing = {index["name"] for index in inspector.get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, [column])


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade of g4h5i6j7k8l9 is not supported. Restore a backup taken before this revision."
    )
