from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from Models.user import User
from client_documents.Schemas.document_request_schema import (
    AdditionalDocumentsCreate,
    DocumentRequestCreate,
    DocumentRequestQueued,
    ResubmissionCreate,
)
from client_documents.Services import document_request_service as service
from client_documents.dependencies import require_client_documents_enabled
from database import get_db
from dependencies import PermissionChecker, get_current_user
from Services.legal_case_service import _require_reviewer

router = APIRouter(prefix="/platform/legal/cases", tags=["Legal and Finance"])


def _reviewer(user: User = Depends(get_current_user)) -> User:
    require_client_documents_enabled()
    _require_reviewer(user)
    return user


@router.post("/{case_id}/document-requests", response_model=DocumentRequestQueued, status_code=202)
def request_documents(
    case_id: int,
    background_tasks: BackgroundTasks,
    data: DocumentRequestCreate | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(_reviewer),
    _: bool = Depends(PermissionChecker("legal:request_documents")),
):
    body = data or DocumentRequestCreate()
    result = service.create_initial_request(db, actor, case_id, confirm_discrepancy=body.confirm_live_recipient, expected_email=body.expected_recipient_email)
    _schedule(background_tasks, result)
    return result


@router.post("/{case_id}/resubmission-requests", response_model=DocumentRequestQueued, status_code=202)
def request_resubmission(
    case_id: int,
    data: ResubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(_reviewer),
    _: bool = Depends(PermissionChecker("legal:request_resubmission")),
):
    result = service.create_resubmission(
        db, actor, case_id, document_ids=data.document_ids, confirm_discrepancy=data.confirm_live_recipient, expected_email=data.expected_recipient_email
    )
    _schedule(background_tasks, result)
    return result


@router.post("/{case_id}/additional-document-requests", response_model=DocumentRequestQueued, status_code=202)
def request_additional(
    case_id: int,
    data: AdditionalDocumentsCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(_reviewer),
    _: bool = Depends(PermissionChecker("legal:request_documents")),
):
    result = service.create_additional(db, actor, case_id, codes=data.codes, confirm_discrepancy=data.confirm_live_recipient, expected_email=data.expected_recipient_email)
    _schedule(background_tasks, result)
    return result


@router.get("/{case_id}/document-requests")
def history(
    case_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_reviewer),
    _: bool = Depends(PermissionChecker("legal:document_requests_view")),
):
    _require_reviewer(actor)
    return service.list_requests(db, case_id)


@router.post("/{case_id}/document-requests/{request_id}/revoke")
def revoke(
    case_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_reviewer),
    _: bool = Depends(PermissionChecker("legal:document_requests_revoke")),
):
    return service.revoke_request(db, actor, case_id, request_id)


def _schedule(background_tasks: BackgroundTasks, result: dict) -> None:
    if result.get("duplicate") or not result.get("email_job_id"):
        return
    from Email.Services.email_task_service import process_email_job
    background_tasks.add_task(process_email_job, result["email_job_id"])
