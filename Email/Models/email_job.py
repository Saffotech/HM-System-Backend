"""Persistent outbound email jobs. Reusable beyond client documents."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class EmailJob(Base):
    __tablename__ = "email_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_email_jobs_idempotency"),)

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(60), nullable=False, index=True)
    case_id = Column(Integer, nullable=True, index=True)
    document_request_id = Column(Integer, nullable=True, index=True)
    recipient_email = Column(String(200), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    subject = Column(String(300), nullable=False)
    template_name = Column(String(80), nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    provider_reference = Column(String(200), nullable=True)
    sanitized_error = Column(String(500), nullable=True)
    idempotency_key = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    processing_owner = Column(String(80), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
