from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from Email.Models.email_job import EmailJob
from Email.Schemas.email_schema import EmailJobOut
from Email.Services.email_job_service import utcnow
from Models.user import User
from Services.role_policy import caller_role_name
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/email/jobs", tags=["Email Jobs"])


def _out(job: EmailJob) -> EmailJobOut:
    return EmailJobOut(
        id=job.id,
        job_type=job.job_type,
        case_id=job.case_id,
        document_request_id=job.document_request_id,
        recipient_email=job.recipient_email,
        recipient_name=job.recipient_name,
        status=job.status,
        attempt_count=job.attempt_count,
        next_retry_at=job.next_retry_at,
        created_at=job.created_at,
        sent_at=job.sent_at,
        sanitized_error=job.sanitized_error,
    )


def _visible(job: EmailJob, user: User) -> bool:
    role = caller_role_name(user)
    if role == "platform_admin":
        return True
    if role == "legal_finance":
        return job.job_type in {
            "document_request",
            "document_resubmission",
            "additional_documents",
            "submission_confirmation",
        }
    return False


@router.get("", response_model=list[EmailJobOut])
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("email_jobs:view")),
):
    rows = db.query(EmailJob).order_by(EmailJob.id.desc()).all()
    visible = [row for row in rows if _visible(row, current_user)]
    start = (page - 1) * page_size
    return [_out(row) for row in visible[start:start + page_size]]


@router.get("/{job_id}", response_model=EmailJobOut)
def read_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("email_jobs:view")),
):
    job = db.query(EmailJob).filter(EmailJob.id == job_id).first()
    if job is None or not _visible(job, current_user):
        raise HTTPException(status_code=404, detail="Email job not found")
    return _out(job)


@router.post("/{job_id}/retry", response_model=EmailJobOut)
def retry_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("email_jobs:retry")),
):
    job = db.query(EmailJob).filter(EmailJob.id == job_id).with_for_update().first()
    if job is None or not _visible(job, current_user):
        raise HTTPException(status_code=404, detail="Email job not found")
    if job.status == "AMBIGUOUS":
        raise HTTPException(status_code=409, detail="Ambiguous jobs require reconciliation, not a normal retry.")
    if job.status not in ("FAILED", "RETRYING"):
        raise HTTPException(status_code=409, detail="This job cannot be retried.")
    if job.attempt_count >= job.max_attempts:
        raise HTTPException(status_code=409, detail="Retry limit reached.")
    job.status = "PENDING"
    job.next_retry_at = utcnow()
    db.commit()
    from Email.Services.email_task_service import process_email_job
    process_email_job(job.id)
    db.refresh(job)
    return _out(job)
