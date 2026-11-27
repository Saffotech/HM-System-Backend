"""Create and claim email jobs. Callers own the transaction unless noted."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from Email.Models.email_job import EmailJob
from Email.Services.payload_crypto import encrypt_payload
from config import settings


def utcnow():
    return datetime.now(timezone.utc)


def queue_job(
    db: Session,
    *,
    job_type: str,
    recipient_email: str,
    recipient_name: str | None,
    subject: str,
    template_name: str,
    template_context: dict,
    idempotency_key: str,
    case_id: int | None = None,
    document_request_id: int | None = None,
) -> EmailJob:
    existing = db.query(EmailJob).filter(EmailJob.idempotency_key == idempotency_key).first()
    if existing is not None:
        return existing
    job = EmailJob(
        job_type=job_type,
        case_id=case_id,
        document_request_id=document_request_id,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        template_name=template_name,
        encrypted_payload=encrypt_payload(json.dumps(template_context)),
        status="PENDING",
        attempt_count=0,
        max_attempts=1 + int(settings.EMAIL_MAX_RETRIES),
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.flush()
    return job


def claim_job(db: Session, job_id: int, owner: str | None = None) -> EmailJob | None:
    owner = owner or uuid.uuid4().hex
    now = utcnow()
    job = (
        db.query(EmailJob)
        .filter(EmailJob.id == job_id)
        .with_for_update()
        .first()
    )
    if job is None:
        return None
    if job.status not in ("PENDING", "RETRYING"):
        return None
    if job.status == "RETRYING" and job.next_retry_at and job.next_retry_at > now:
        return None
    job.status = "PROCESSING"
    job.processing_owner = owner
    job.processing_started_at = now
    job.processing_lease_expires_at = now + timedelta(seconds=settings.EMAIL_PROCESSING_LEASE_SECONDS)
    job.updated_at = now
    db.flush()
    return job


def mark_sent(db: Session, job: EmailJob, reference: str | None) -> None:
    now = utcnow()
    job.status = "SENT"
    job.provider_reference = reference
    job.sent_at = now
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.encrypted_payload = encrypt_payload("{}")
    job.updated_at = now


def mark_retry(db: Session, job: EmailJob, error: str, delay_seconds: int) -> None:
    now = utcnow()
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.sanitized_error = (error or "")[:500]
    job.updated_at = now
    if job.attempt_count >= job.max_attempts:
        job.status = "FAILED"
        job.failed_at = now
        return
    job.status = "RETRYING"
    job.next_retry_at = now + timedelta(seconds=delay_seconds)


def mark_failed(db: Session, job: EmailJob, error: str, *, ambiguous: bool = False) -> None:
    now = utcnow()
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.status = "AMBIGUOUS" if ambiguous else "FAILED"
    job.sanitized_error = (error or "")[:500]
    job.failed_at = now
    job.updated_at = now


def cancel_job(db: Session, job: EmailJob, reason: str) -> None:
    if job.status in ("SENT", "FAILED", "CANCELLED"):
        return
    job.status = "CANCELLED"
    job.sanitized_error = reason[:500]
    job.updated_at = utcnow()
