from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class DocumentType(Base):
    __tablename__ = "document_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    requirement_type = Column(String(30), nullable=False, index=True)
    is_required = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    allowed_file_types = Column(String(200), nullable=False, default=".pdf,.jpg,.jpeg,.png,.webp")
    max_file_size_mb = Column(Integer, nullable=False, default=5)
    display_order = Column(Integer, nullable=False, default=0)
    linked_checklist_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class DocumentUploadRequest(Base):
    __tablename__ = "document_upload_requests"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    request_type = Column(String(30), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    recipient_email = Column(String(200), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    recipient_source = Column(String(40), nullable=False)
    hospital_name_snapshot = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


Index(
    "uq_one_active_document_request",
    DocumentUploadRequest.case_id,
    unique=True,
    postgresql_where=text("status = 'ACTIVE'"),
)


class DocumentUploadRequestItem(Base):
    __tablename__ = "document_upload_request_items"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("document_upload_requests.id"), nullable=False, index=True)
    document_type_id = Column(Integer, ForeignKey("document_types.id"), nullable=True)
    document_code = Column(String(80), nullable=False)
    document_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    requirement_type = Column(String(30), nullable=False)
    is_required = Column(Boolean, nullable=False, default=True)
    allowed_file_types = Column(String(200), nullable=False)
    max_file_size_mb = Column(Integer, nullable=False, default=5)
    display_order = Column(Integer, nullable=False, default=0)
    review_remarks = Column(Text, nullable=True)
    replacement_document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=True)


class TemporaryDocumentUpload(Base):
    __tablename__ = "temporary_document_uploads"
    __table_args__ = (
        UniqueConstraint("request_id", "request_item_id", name="uq_temp_upload_request_item"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("document_upload_requests.id"), nullable=False, index=True)
    request_item_id = Column(Integer, ForeignKey("document_upload_request_items.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    mime_type = Column(String(120), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class DocumentReviewHistory(Base):
    __tablename__ = "document_review_history"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    previous_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=False)
    remarks = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
