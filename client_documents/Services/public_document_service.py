"""Public upload staging and final submission."""
import json
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from Models.legal_case import LegalCase, LegalDocument
from Services.legal_case_service import _sync_checklist_from_documents
from client_documents.Models.models import DocumentReviewHistory, TemporaryDocumentUpload
from client_documents.Services.document_request_service import load_public, queue_confirmation, utcnow
from client_documents.Services.document_storage_service import delete_if_exists, save_private
from client_documents.Utils.file_validator import FileValidationError, sanitize_filename, validate_bytes
from config import settings


_UPLOAD_HITS: dict[str, list[float]] = {}


def _limit_uploads(token_hash: str) -> None:
    import time
    now = time.time()
    hits = [stamp for stamp in _UPLOAD_HITS.get(token_hash, []) if now - stamp < 60]
    if len(hits) >= 30:
        raise HTTPException(status_code=429, detail="Too many uploads for this link.")
    hits.append(now)
    _UPLOAD_HITS[token_hash] = hits


def _reject_unscanned_production_upload() -> None:
    # MALWARE_SCAN_ENFORCED does not enable uploads. No scanner is implemented.
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=503,
            detail="Client uploads are disabled until a malware scanner is configured and enforced.",
        )


async def stage_upload(db: Session, token_hash: str, item_id: int, file: UploadFile) -> dict:
    _reject_unscanned_production_upload()
    _limit_uploads(token_hash)
    request, items = load_public(db, token_hash)
    item = next((row for row in items if row.id == item_id), None)
    if item is None or item.requirement_type != "CLIENT_UPLOAD":
        raise HTTPException(status_code=404, detail="Document requirement not found")
    if item.replacement_document_id:
        target = db.query(LegalDocument).filter(LegalDocument.id == item.replacement_document_id).first()
        if target is not None and target.status == "Verified":
            raise HTTPException(status_code=409, detail="A verified document cannot be replaced.")
    content = await file.read()
    allowed = {part.strip().lower() for part in item.allowed_file_types.split(",") if part.strip()}
    limit = min(item.max_file_size_mb, settings.DOCUMENT_MAX_FILE_SIZE_MB) * 1024 * 1024
    try:
        suffix, mime = validate_bytes(content, file.filename or "", allowed, limit)
    except FileValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_private(request.case_id, suffix, content)
    existing = (
        db.query(TemporaryDocumentUpload)
        .filter(TemporaryDocumentUpload.request_id == request.id, TemporaryDocumentUpload.request_item_id == item.id)
        .first()
    )
    if existing is not None:
        delete_if_exists(existing.stored_path)
        existing.original_filename = sanitize_filename(file.filename)
        existing.stored_path = str(path)
        existing.mime_type = mime
        existing.file_size_bytes = len(content)
    else:
        db.add(TemporaryDocumentUpload(
            request_id=request.id,
            request_item_id=item.id,
            original_filename=sanitize_filename(file.filename),
            stored_path=str(path),
            mime_type=mime,
            file_size_bytes=len(content),
        ))
    db.commit()
    return {"item_id": item.id, "status": "STAGED"}


def submit_request(db: Session, token_hash: str) -> dict:
    _reject_unscanned_production_upload()
    request, items = load_public(db, token_hash)
    request = (
        db.query(type(request))
        .filter_by(id=request.id)
        .with_for_update()
        .one()
    )
    if request.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="This request is already closed.")
    staged = {
        row.request_item_id: row
        for row in db.query(TemporaryDocumentUpload).filter(TemporaryDocumentUpload.request_id == request.id).all()
    }
    for item in items:
        if item.is_required and item.id not in staged:
            raise HTTPException(status_code=422, detail=f"Required document missing: {item.document_name}")
    case = db.query(LegalCase).filter(LegalCase.id == request.case_id).first()
    names = []
    touched = set()
    for item in items:
        temp = staged.get(item.id)
        if temp is None:
            continue
        if item.replacement_document_id:
            previous = db.query(LegalDocument).filter(LegalDocument.id == item.replacement_document_id).with_for_update().first()
            if previous is None or previous.case_id != case.id:
                raise HTTPException(status_code=409, detail="Replacement target is not valid.")
            if previous.status == "Verified" or not previous.is_current:
                raise HTTPException(status_code=409, detail="A verified document cannot be replaced.")
            previous.is_current = False
            version = int(previous.version or 1) + 1
            replaces = previous.id
        else:
            version = 1
            replaces = None
        document = LegalDocument(
            case_id=case.id,
            category=item.document_name,
            file_name=temp.original_filename,
            stored_path=temp.stored_path,
            status="Pending Review",
            uploaded_by=None,
            document_type_id=item.document_type_id,
            mime_type=temp.mime_type,
            file_size_bytes=temp.file_size_bytes,
            upload_source="CLIENT",
            upload_request_id=request.id,
            version=version,
            replaces_document_id=replaces,
            is_current=True,
        )
        db.add(document)
        db.flush()
        db.add(DocumentReviewHistory(
            document_id=document.id,
            reviewer_id=None,
            previous_status=None,
            new_status="Pending Review",
            remarks=None,
            version=version,
        ))
        names.append(item.document_name)
        touched.add(item.document_name)
    if case.status == "New from CRM":
        case.status = "In Review"
    db.flush()
    db.expire(case, ["documents"])
    class _ClientActor:
        id = None
        tenant_id = None
        role_obj = None
        email = None
    try:
        _sync_checklist_from_documents(case, _ClientActor(), touched)
    except Exception:
        pass
    request.status = "COMPLETED"
    request.completed_at = utcnow()
    job_id = queue_confirmation(db, request, names)
    db.commit()
    return {"message": "Documents submitted", "request_id": request.id, "email_job_id": job_id}


def public_view(db: Session, token_hash: str) -> dict:
    request, items = load_public(db, token_hash)
    staged = {
        row.request_item_id
        for row in db.query(TemporaryDocumentUpload).filter(TemporaryDocumentUpload.request_id == request.id).all()
    }
    return {
        "hospital_name": request.hospital_name_snapshot,
        "expires_at": request.expires_at,
        "requirements": [
            {
                "item_id": item.id,
                "code": item.document_code,
                "name": item.document_name,
                "description": item.description,
                "is_required": item.is_required,
                "allowed_file_types": [part.strip() for part in item.allowed_file_types.split(",") if part.strip()],
                "max_file_size_mb": item.max_file_size_mb,
                "status": "UPLOADED" if item.id in staged else "MISSING",
                "display_order": item.display_order,
                "remarks": item.review_remarks,
            }
            for item in items
        ],
    }
