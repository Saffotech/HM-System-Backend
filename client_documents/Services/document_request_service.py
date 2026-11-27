"""Document request orchestration. Email transport stays in Email/."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Email.Services.email_job_service import cancel_job, queue_job
from Email.Services.payload_crypto import PayloadCryptoError
from Models.lead import Lead
from Models.legal_case import LegalCase, LegalDocument
from Models.user import User
from Services.audit_service import log_event
from client_documents.Models.models import (
    DocumentUploadRequest,
    DocumentUploadRequestItem,
    TemporaryDocumentUpload,
)
from client_documents.Services.document_type_service import active_uploads, seed_document_types
from client_documents.Utils.secure_token import generate_token
from config import settings

DECIDED = ("Approved", "Rejected", "Conditionally Approved")
CLOSED_LEADS = ("Not Interested", "Registered")


def utcnow():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def effective_status(request: DocumentUploadRequest, now=None) -> str:
    now = now or utcnow()
    if request.status == "ACTIVE" and _aware(request.expires_at) <= now:
        return "EXPIRED"
    return request.status


def resolve_recipient(case: LegalCase, lead: Lead, *, confirm_discrepancy: bool, expected_email: str | None = None) -> tuple[str, str, str]:
    contact = (lead.contact_email or "").strip().lower()
    hospital = (lead.hospital_email or "").strip().lower()
    if contact:
        email, source, snapshot = contact, "lead.contact_email", (case.contact_email or "").strip().lower()
    elif hospital:
        email, source, snapshot = hospital, "lead.hospital_email", (case.hospital_email or "").strip().lower()
    else:
        raise HTTPException(status_code=422, detail="A contact email or hospital email is required before documents can be requested.")
    if "@" not in email or " " in email:
        raise HTTPException(status_code=422, detail="The lead email address is not valid.")
    if snapshot and snapshot != email:
        if not confirm_discrepancy:
            raise HTTPException(
                status_code=409,
                detail=f"The live lead email {email} differs from the legal case snapshot {snapshot}. Confirm that exact address before sending.",
            )
        if (expected_email or "").strip().lower() != email:
            raise HTTPException(status_code=409, detail="Confirmation must name the exact live recipient email.")
    name = (lead.contact_person or case.contact_person or "Client").strip()
    return email, name, source


def assert_case_eligible(case: LegalCase, lead: Lead) -> None:
    if lead.status in CLOSED_LEADS:
        raise HTTPException(status_code=409, detail="Documents cannot be requested for this lead.")
    if case.status in DECIDED:
        raise HTTPException(status_code=409, detail="This case already has a decision.")


def _load_pair(db: Session, case_id: int) -> tuple[LegalCase, Lead]:
    case = db.query(LegalCase).filter(LegalCase.id == case_id).with_for_update().first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    lead = db.query(Lead).filter(Lead.id == case.lead_id).with_for_update().first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return case, lead


def _expire_stale(db: Session, case_id: int) -> None:
    now = utcnow()
    rows = (
        db.query(DocumentUploadRequest)
        .filter(DocumentUploadRequest.case_id == case_id, DocumentUploadRequest.status == "ACTIVE")
        .all()
    )
    for row in rows:
        if _aware(row.expires_at) <= now:
            row.status = "EXPIRED"


def _active(db: Session, case_id: int) -> DocumentUploadRequest | None:
    _expire_stale(db, case_id)
    return (
        db.query(DocumentUploadRequest)
        .filter(DocumentUploadRequest.case_id == case_id, DocumentUploadRequest.status == "ACTIVE")
        .first()
    )


def _items(db: Session, request_id: int) -> list[DocumentUploadRequestItem]:
    return (
        db.query(DocumentUploadRequestItem)
        .filter(DocumentUploadRequestItem.request_id == request_id)
        .order_by(DocumentUploadRequestItem.display_order.asc())
        .all()
    )


def _context(raw_token: str, request: DocumentUploadRequest, items, template: str) -> dict:
    upload_url = f"{settings.FRONTEND_URL.rstrip('/')}/documents/upload?token={raw_token}"
    docs = [
        {"name": item.document_name, "description": item.description or "", "remarks": item.review_remarks or ""}
        for item in items
    ]
    if template == "document_request.html":
        return {
            "client_name": request.recipient_name,
            "hospital_name": request.hospital_name_snapshot,
            "required_documents": [row for row, item in zip(docs, items) if item.is_required],
            "optional_documents": [row for row, item in zip(docs, items) if not item.is_required],
            "upload_url": upload_url,
            "expires_at": request.expires_at.isoformat(),
        }
    if template == "document_resubmission.html":
        return {
            "client_name": request.recipient_name,
            "hospital_name": request.hospital_name_snapshot,
            "documents": docs,
            "upload_url": upload_url,
            "expires_at": request.expires_at.isoformat(),
        }
    return {
        "client_name": request.recipient_name,
        "hospital_name": request.hospital_name_snapshot,
        "document_names": [item.document_name for item in items],
        "submitted_at": utcnow().isoformat(),
    }


def _queue(db, request, items, raw_token, template, job_type) -> int:
    try:
        job = queue_job(
            db,
            job_type=job_type,
            recipient_email=request.recipient_email,
            recipient_name=request.recipient_name,
            subject=_subject(job_type),
            template_name=template,
            template_context=_context(raw_token, request, items, template),
            idempotency_key=f"{job_type}:{request.id}",
            case_id=request.case_id,
            document_request_id=request.id,
        )
    except PayloadCryptoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return job.id


def _subject(job_type: str) -> str:
    if job_type == "document_resubmission":
        return "SaffoCare — Document Resubmission Required"
    if job_type == "submission_confirmation":
        return "SaffoCare — Documents Received"
    return "SaffoCare — Required Documents for Hospital Onboarding"


def create_initial_request(db: Session, actor: User, case_id: int, *, confirm_discrepancy: bool, expected_email: str | None = None) -> dict:
    case, lead = _load_pair(db, case_id)
    assert_case_eligible(case, lead)
    email, name, source = resolve_recipient(case, lead, confirm_discrepancy=confirm_discrepancy, expected_email=expected_email)
    seed_document_types(db)
    types = active_uploads(db)
    if not types:
        raise HTTPException(status_code=422, detail="No client document requirements are configured.")
    signature = tuple(row.code for row in types)
    current = _active(db, case.id)
    if current is not None and current.request_type == "INITIAL":
        current_codes = tuple(item.document_code for item in _items(db, current.id))
        if current_codes == signature and current.recipient_email == email:
            from Email.Models.email_job import EmailJob
            job = db.query(EmailJob).filter(EmailJob.document_request_id == current.id).first()
            return _result(current, job.id if job else None, job.status if job else None, duplicate=True)
        raise HTTPException(status_code=409, detail="An active document request already exists. Revoke it before sending a different request.")
    if current is not None:
        raise HTTPException(status_code=409, detail="An active document request already exists.")
    raw, digest = generate_token()
    request = DocumentUploadRequest(
        case_id=case.id,
        requested_by=actor.id,
        request_type="INITIAL",
        token_hash=digest,
        recipient_email=email,
        recipient_name=name,
        recipient_source=source,
        hospital_name_snapshot=case.hospital_name or lead.hospital_name,
        status="ACTIVE",
        expires_at=utcnow() + timedelta(hours=settings.DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS),
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active document request already exists.")
    items = []
    for row in types:
        item = DocumentUploadRequestItem(
            request_id=request.id,
            document_type_id=row.id,
            document_code=row.code,
            document_name=row.name,
            description=row.description,
            requirement_type="CLIENT_UPLOAD",
            is_required=bool(row.is_required),
            allowed_file_types=row.allowed_file_types,
            max_file_size_mb=min(row.max_file_size_mb, settings.DOCUMENT_MAX_FILE_SIZE_MB),
            display_order=row.display_order,
        )
        db.add(item)
        items.append(item)
    db.flush()
    job_id = _queue(db, request, items, raw, "document_request.html", "document_request")
    log_event(db, actor=actor, action="document_request.create", resource_type="legal_case", resource_id=case.id, summary=f"Queued document request {request.id}", details={"request_id": request.id, "recipient_source": source})
    return _result(request, job_id, "PENDING", duplicate=False)


def create_resubmission(db: Session, actor: User, case_id: int, *, document_ids: list[int], confirm_discrepancy: bool, expected_email: str | None = None) -> dict:
    case, lead = _load_pair(db, case_id)
    assert_case_eligible(case, lead)
    email, name, source = resolve_recipient(case, lead, confirm_discrepancy=confirm_discrepancy, expected_email=expected_email)
    seed_document_types(db)
    selected = set(document_ids or [])
    outstanding = []
    current_docs = [doc for doc in case.documents if getattr(doc, "is_current", True)]
    by_category = {}
    for doc in current_docs:
        by_category.setdefault(doc.category, []).append(doc)
    types = {row.name: row for row in active_uploads(db)}
    for row in types.values():
        docs = by_category.get(row.name, [])
        if not docs:
            outstanding.append((row, None, "Missing"))
            continue
        for doc in docs:
            if doc.status == "Verified":
                continue
            if doc.status == "Changes Requested" or doc.id in selected:
                if doc.status == "Pending Review" and doc.id not in selected:
                    continue
                outstanding.append((row, doc, doc.review_remarks))
    if not outstanding:
        raise HTTPException(status_code=422, detail="No documents are eligible for resubmission.")
    current = _active(db, case.id)
    if current is not None:
        current.status = "REVOKED"
        current.revoked_at = utcnow()
        _cancel_jobs(db, current.id, "Superseded by a new request")
    raw, digest = generate_token()
    request = DocumentUploadRequest(
        case_id=case.id,
        requested_by=actor.id,
        request_type="RESUBMISSION",
        token_hash=digest,
        recipient_email=email,
        recipient_name=name,
        recipient_source=source,
        hospital_name_snapshot=case.hospital_name or lead.hospital_name,
        status="ACTIVE",
        expires_at=utcnow() + timedelta(hours=settings.DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS),
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active document request already exists.")
    items = []
    for row, doc, remarks in outstanding:
        item = DocumentUploadRequestItem(
            request_id=request.id,
            document_type_id=row.id,
            document_code=row.code,
            document_name=row.name,
            description=row.description,
            requirement_type="CLIENT_UPLOAD",
            is_required=True,
            allowed_file_types=row.allowed_file_types,
            max_file_size_mb=min(row.max_file_size_mb, settings.DOCUMENT_MAX_FILE_SIZE_MB),
            display_order=row.display_order,
            review_remarks=remarks if isinstance(remarks, str) else None,
            replacement_document_id=doc.id if doc else None,
        )
        db.add(item)
        items.append(item)
    db.flush()
    job_id = _queue(db, request, items, raw, "document_resubmission.html", "document_resubmission")
    log_event(db, actor=actor, action="document_request.resubmit", resource_type="legal_case", resource_id=case.id, summary=f"Queued resubmission {request.id}", details={"request_id": request.id})
    return _result(request, job_id, "PENDING", duplicate=False)


def create_additional(db: Session, actor: User, case_id: int, *, codes: list[str], confirm_discrepancy: bool, expected_email: str | None = None) -> dict:
    case, lead = _load_pair(db, case_id)
    assert_case_eligible(case, lead)
    email, name, source = resolve_recipient(case, lead, confirm_discrepancy=confirm_discrepancy, expected_email=expected_email)
    seed_document_types(db)
    wanted = {code.strip().upper() for code in codes}
    rows = [row for row in active_uploads(db) if row.code in wanted]
    if len(rows) != len(wanted) or not rows:
        raise HTTPException(status_code=422, detail="Choose active client-upload document types.")
    current = _active(db, case.id)
    if current is not None:
        current.status = "REVOKED"
        current.revoked_at = utcnow()
        _cancel_jobs(db, current.id, "Superseded by additional documents")
    raw, digest = generate_token()
    request = DocumentUploadRequest(
        case_id=case.id,
        requested_by=actor.id,
        request_type="ADDITIONAL_DOCUMENTS",
        token_hash=digest,
        recipient_email=email,
        recipient_name=name,
        recipient_source=source,
        hospital_name_snapshot=case.hospital_name or lead.hospital_name,
        status="ACTIVE",
        expires_at=utcnow() + timedelta(hours=settings.DOCUMENT_UPLOAD_LINK_EXPIRY_HOURS),
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active document request already exists.")
    items = []
    for row in rows:
        item = DocumentUploadRequestItem(
            request_id=request.id,
            document_type_id=row.id,
            document_code=row.code,
            document_name=row.name,
            description=row.description,
            requirement_type="CLIENT_UPLOAD",
            is_required=bool(row.is_required),
            allowed_file_types=row.allowed_file_types,
            max_file_size_mb=min(row.max_file_size_mb, settings.DOCUMENT_MAX_FILE_SIZE_MB),
            display_order=row.display_order,
        )
        db.add(item)
        items.append(item)
    db.flush()
    job_id = _queue(db, request, items, raw, "document_request.html", "additional_documents")
    log_event(db, actor=actor, action="document_request.additional", resource_type="legal_case", resource_id=case.id, summary=f"Queued additional documents {request.id}", details={"request_id": request.id})
    return _result(request, job_id, "PENDING", duplicate=False)


def list_requests(db: Session, case_id: int) -> list[dict]:
    rows = (
        db.query(DocumentUploadRequest)
        .filter(DocumentUploadRequest.case_id == case_id)
        .order_by(DocumentUploadRequest.id.desc())
        .all()
    )
    from Email.Models.email_job import EmailJob
    result = []
    for row in rows:
        job = db.query(EmailJob).filter(EmailJob.document_request_id == row.id).order_by(EmailJob.id.desc()).first()
        result.append({
            "request_id": row.id,
            "request_type": row.request_type,
            "status": effective_status(row),
            "recipient_email": row.recipient_email,
            "categories": [item.document_name for item in _items(db, row.id)],
            "requested_by": row.requested_by,
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "completed_at": row.completed_at,
            "email_status": job.status if job else None,
        })
    return result


def revoke_request(db: Session, actor: User, case_id: int, request_id: int) -> dict:
    row = (
        db.query(DocumentUploadRequest)
        .filter(DocumentUploadRequest.id == request_id, DocumentUploadRequest.case_id == case_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Document request not found")
    if effective_status(row) != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only an active request can be revoked.")
    row.status = "REVOKED"
    row.revoked_at = utcnow()
    _cancel_jobs(db, row.id, "Revoked")
    log_event(db, actor=actor, action="document_request.revoke", resource_type="legal_case", resource_id=case_id, summary=f"Revoked document request {row.id}", details={"request_id": row.id})
    return {"request_id": row.id, "status": "REVOKED"}


def _cancel_jobs(db: Session, request_id: int, reason: str) -> None:
    from Email.Models.email_job import EmailJob
    for job in db.query(EmailJob).filter(EmailJob.document_request_id == request_id).all():
        if job.job_type == "submission_confirmation":
            continue
        cancel_job(db, job, reason)


def _result(request, job_id, status, duplicate: bool) -> dict:
    return {
        "message": "Existing document request" if duplicate else "Document request queued",
        "case_id": request.case_id,
        "request_id": request.id,
        "recipient_email": request.recipient_email,
        "email_job_id": job_id,
        "email_status": status,
        "expires_at": request.expires_at,
        "duplicate": duplicate,
    }


def email_still_allowed(db: Session, request_id: int, recipient_email: str | None) -> str | None:
    request = db.query(DocumentUploadRequest).filter(DocumentUploadRequest.id == request_id).first()
    if request is None:
        return "Request missing"
    if effective_status(request) != "ACTIVE":
        return "Upload link is no longer active"
    lead = db.query(Lead).join(LegalCase, LegalCase.lead_id == Lead.id).filter(LegalCase.id == request.case_id).first()
    if lead is None:
        return "Lead missing"
    live = (lead.contact_email or lead.hospital_email or "").strip().lower()
    if recipient_email and live and recipient_email.lower() != live and recipient_email.lower() != (lead.hospital_email or "").lower() and recipient_email.lower() != (lead.contact_email or "").lower():
        return "Recipient changed"
    return None


def invalidate_for_lead_email_change(db: Session, lead_id: int) -> None:
    cases = db.query(LegalCase).filter(LegalCase.lead_id == lead_id).all()
    for case in cases:
        current = _active(db, case.id)
        if current is None:
            continue
        current.status = "REVOKED"
        current.revoked_at = utcnow()
        _cancel_jobs(db, current.id, "Recipient changed")


def queue_confirmation(db: Session, request: DocumentUploadRequest, names: list[str]) -> int:
    context = {
        "client_name": request.recipient_name,
        "hospital_name": request.hospital_name_snapshot,
        "document_names": names,
        "submitted_at": utcnow().isoformat(),
    }
    try:
        job = queue_job(
            db,
            job_type="submission_confirmation",
            recipient_email=request.recipient_email,
            recipient_name=request.recipient_name,
            subject=_subject("submission_confirmation"),
            template_name="submission_confirmation.html",
            template_context=context,
            idempotency_key=f"submission_confirmation:{request.id}",
            case_id=request.case_id,
            document_request_id=request.id,
        )
    except PayloadCryptoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return job.id


def load_public(db: Session, token_hash: str) -> tuple[DocumentUploadRequest, list[DocumentUploadRequestItem]]:
    request = db.query(DocumentUploadRequest).filter(DocumentUploadRequest.token_hash == token_hash).first()
    if request is None:
        raise HTTPException(status_code=401, detail="Invalid upload link")
    status = effective_status(request)
    if status != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"Upload link is {status.lower()}")
    case = db.query(LegalCase).filter(LegalCase.id == request.case_id).first()
    lead = db.query(Lead).filter(Lead.id == case.lead_id).first() if case else None
    if case is None or lead is None or lead.status in CLOSED_LEADS or case.status in DECIDED:
        raise HTTPException(status_code=403, detail="This case cannot accept documents.")
    blocked = email_still_allowed(db, request.id, request.recipient_email)
    if blocked == "Recipient changed":
        raise HTTPException(status_code=403, detail="This upload link is no longer valid.")
    return request, _items(db, request.id)
