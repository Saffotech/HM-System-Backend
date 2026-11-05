from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.legal_case_schema import (
    EscalationDecision,
    LegalCaseOut,
    LegalChecklistUpdate,
    LegalDecision,
    LegalFinanceUpdate,
)
from Services.legal_case_service import (
    add_document,
    confirm_advance,
    decide_case,
    decide_escalation,
    download_document,
    get_case,
    list_cases,
    request_escalation,
    resubmit_case,
    save_checklist,
    save_finance,
    set_document_status,
)
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/legal/cases", tags=["Legal and Finance"])


@router.get("", response_model=list[LegalCaseOut])
def read_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return list_cases(db, current_user)


@router.get("/{case_id}", response_model=LegalCaseOut)
def read_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return get_case(db, current_user, case_id)


@router.patch("/{case_id}/checklist", response_model=LegalCaseOut)
def update_checklist(
    case_id: int,
    data: LegalChecklistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return save_checklist(db, current_user, case_id, data)


@router.patch("/{case_id}/finance", response_model=LegalCaseOut)
def update_finance(
    case_id: int,
    data: LegalFinanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return save_finance(db, current_user, case_id, data)


@router.post("/{case_id}/escalation/request", response_model=LegalCaseOut)
def ask_for_escalation(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return request_escalation(db, current_user, case_id)


@router.post("/{case_id}/escalation", response_model=LegalCaseOut)
def record_escalation(
    case_id: int,
    data: EscalationDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return decide_escalation(db, current_user, case_id, data)


@router.post("/{case_id}/documents", response_model=LegalCaseOut)
async def upload_document(
    case_id: int,
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return await add_document(db, current_user, case_id, category, file)


@router.get("/{case_id}/documents/{document_id}")
def read_document(
    case_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return download_document(db, current_user, case_id, document_id)


@router.post("/{case_id}/documents/{document_id}/verify", response_model=LegalCaseOut)
def verify_document(
    case_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return set_document_status(db, current_user, case_id, document_id, "Verified")


@router.post("/{case_id}/documents/{document_id}/request-changes", response_model=LegalCaseOut)
def request_document_changes(
    case_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return set_document_status(db, current_user, case_id, document_id, "Changes Requested")


@router.post("/{case_id}/decision", response_model=LegalCaseOut)
def record_decision(
    case_id: int,
    data: LegalDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return decide_case(db, current_user, case_id, data)


@router.post("/{case_id}/resubmit", response_model=LegalCaseOut)
def resubmit(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal:review")),
):
    return resubmit_case(db, current_user, case_id)


@router.post("/{case_id}/payment-confirmation", response_model=LegalCaseOut)
@router.post("/{case_id}/advance", response_model=LegalCaseOut)
def record_advance(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("registrations:create")),
):
    return confirm_advance(db, current_user, case_id)
