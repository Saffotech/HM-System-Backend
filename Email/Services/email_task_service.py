"""Background execution and lightweight recovery for email jobs."""
import json
import logging
import random
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from Email.Models.email_job import EmailJob
from Email.Services.email_job_service import claim_job, mark_failed, mark_retry, mark_sent
from Email.Services.email_service import EmailTransport
from Email.Services.email_template_service import render
from Email.Services.payload_crypto import PayloadCryptoError, decrypt_payload
from config import settings
from database import SessionLocal

logger = logging.getLogger(__name__)
_recovery_started = False
_transport = EmailTransport()


def set_transport(transport: EmailTransport) -> None:
    global _transport
    _transport = transport


def _eligible(db: Session, job: EmailJob, context: dict) -> str | None:
    if job.job_type == "submission_confirmation":
        return None
    if not job.document_request_id:
        return None
    from client_documents.Services.document_request_service import email_still_allowed

    return email_still_allowed(db, job.document_request_id, job.recipient_email)


def process_email_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = claim_job(db, job_id)
        if job is None:
            db.commit()
            return
        try:
            context = json.loads(decrypt_payload(job.encrypted_payload))
        except PayloadCryptoError:
            mark_failed(db, job, "Payload could not be decrypted")
            db.commit()
            return
        reason = _eligible(db, job, context)
        if reason:
            from Email.Services.email_job_service import cancel_job
            cancel_job(db, job, reason)
            db.commit()
            return
        html = render(job.template_name, context)
        recipient_email = job.recipient_email
        recipient_name = job.recipient_name
        subject = job.subject
        text_body = context.get("text_body")
        db.commit()
        db.close()
        db = None
        try:
            result = _transport.send(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                html_body=html,
                text_body=text_body,
            )
        except Exception:
            logger.exception("Email job %s provider outcome is uncertain", job_id)
            db = SessionLocal()
            job = db.query(EmailJob).filter(EmailJob.id == job_id).one()
            mark_failed(db, job, "Provider outcome is uncertain", ambiguous=True)
            db.commit()
            return
        db = SessionLocal()
        job = db.query(EmailJob).filter(EmailJob.id == job_id).one()
        if result.outcome == "accepted":
            mark_sent(db, job, result.provider_reference)
        elif result.outcome == "temporary":
            delay = result.retry_after_seconds or _backoff(job.attempt_count)
            mark_retry(db, job, result.error or "Temporary provider failure", delay)
        elif result.outcome == "ambiguous":
            mark_failed(db, job, result.error or "Ambiguous provider result", ambiguous=True)
        else:
            mark_failed(db, job, result.error or "Permanent provider failure")
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Email job %s failed", job_id)
    finally:
        if db is not None:
            db.close()


def _backoff(attempt: int) -> int:
    base = settings.EMAIL_RETRY_DELAY_SECONDS * (2 ** max(int(attempt or 0), 0))
    return int(base + random.randint(0, settings.EMAIL_RETRY_DELAY_SECONDS))


def recover_due_jobs(db: Session, limit: int = 20) -> list[int]:
    """Select due jobs in the database, then apply the batch limit.

    AMBIGUOUS, FAILED, SENT, and CANCELLED jobs are not eligible. A future
    retry time is not eligible. An expired PROCESSING lease means the provider
    call may already have been accepted, so the job becomes AMBIGUOUS and is
    not sent again.
    """
    from sqlalchemy import or_

    now = datetime.now(timezone.utc)
    expired = (
        db.query(EmailJob)
        .filter(
            EmailJob.status == "PROCESSING",
            EmailJob.processing_lease_expires_at.isnot(None),
            EmailJob.processing_lease_expires_at <= now,
        )
        .all()
    )
    for job in expired:
        mark_failed(db, job, "Processing lease expired before the provider result was recorded", ambiguous=True)
    db.flush()
    rows = (
        db.query(EmailJob.id)
        .filter(
            or_(
                EmailJob.status == "PENDING",
                (EmailJob.status == "RETRYING")
                & (or_(EmailJob.next_retry_at.is_(None), EmailJob.next_retry_at <= now)),
            )
        )
        .order_by(EmailJob.id.asc())
        .limit(limit)
        .all()
    )
    db.commit()
    return [row[0] for row in rows]


def _loop() -> None:
    while True:
        if settings.EMAIL_RECOVERY_ENABLED:
            db = SessionLocal()
            try:
                ids = recover_due_jobs(db)
            except Exception:
                db.rollback()
                logger.exception("Email recovery failed")
                ids = []
            finally:
                db.close()
            for job_id in ids:
                process_email_job(job_id)
        threading.Event().wait(max(settings.EMAIL_RECOVERY_INTERVAL_SECONDS, 5))


def start_email_recovery() -> None:
    global _recovery_started
    if _recovery_started or not settings.EMAIL_RECOVERY_ENABLED:
        return
    _recovery_started = True
    threading.Thread(target=_loop, name="email-recovery", daemon=True).start()
