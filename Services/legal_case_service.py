"""Legal and Finance sits between an agreed CRM lead and hospital registration."""
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from Models.lead import Lead
from Models.legal_case import LegalCase, LegalCaseDecision, LegalChecklistItem, LegalDocument, LegalFinanceTerms
from Models.user import User
from Schemas.legal_case_schema import (
    ChecklistItemOut,
    EscalationDecision,
    LegalCaseOut,
    LegalChecklistUpdate,
    LegalDecision,
    LegalDecisionOut,
    LegalDocumentOut,
    LegalFinanceOut,
    LegalFinanceUpdate,
)
from Services.role_policy import caller_role_name

IST = ZoneInfo("Asia/Kolkata")
HOSPITAL_CHECKLIST = (
    "Legal entity identity verified",
    "Hospital registration documents reviewed",
    "Hospital address checked",
    "Authorized signatory verified",
    "Relevant licenses checked (where applicable)",
    "Agreement and data protection terms reviewed",
    "Contract signing requirements checked",
)
DOCUMENT_CATEGORIES = (
    "Hospital Registration",
    "Entity Registration",
    "Authorized Representative",
    "Tax / GST Details",
    "Hospital License",
    "Service Agreement",
)
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 5 * 1024 * 1024


def _now():
    return datetime.now(IST)


def _role(actor: User) -> str:
    if actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Legal and Finance is only available to platform staff")
    return caller_role_name(actor)


def _require_reviewer(actor: User) -> None:
    if _role(actor) != "legal_finance":
        raise HTTPException(status_code=403, detail="Only Legal and Finance can review cases")


def _upload_dir() -> Path:
    folder = Path(os.getenv("LEGAL_UPLOAD_DIR", "uploads/legal_documents"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def open_case_for_agreed_lead(db: Session, lead: Lead) -> LegalCase:
    """One agreed hospital lead gets one case. A second call returns the same row."""
    existing = db.query(LegalCase).filter(LegalCase.lead_id == lead.id).first()
    if existing is not None:
        return existing
    case = LegalCase(
        lead_id=lead.id,
        hospital_name=lead.hospital_name,
        city=lead.city,
        plan=lead.plan,
        status="New from CRM",
        advance_received=False,
        discount=0,
    )
    db.add(case)
    db.flush()
    for label in HOSPITAL_CHECKLIST:
        db.add(LegalChecklistItem(case_id=case.id, label=label, status="Pending"))
    db.add(LegalFinanceTerms(case_id=case.id))
    db.flush()
    return case


def _when(value) -> str | None:
    return value.isoformat() if value else None


def _finance_out(terms: LegalFinanceTerms | None) -> LegalFinanceOut | None:
    if terms is None:
        return None
    return LegalFinanceOut(
        standard_price=terms.standard_price,
        discount=terms.discount,
        years=terms.years,
        implementation_fee=terms.implementation_fee,
        training_fee=terms.training_fee,
        tax_percent=terms.tax_percent,
        advance_percent=terms.advance_percent,
        credit_days=terms.credit_days,
        frequency=terms.frequency,
        modules=terms.modules,
        gstin=terms.gstin,
        po_required=terms.po_required,
        invoice_email=terms.invoice_email,
        reviewed=bool(terms.reviewed),
        updated_by=terms.updated_by,
        updated_at=_when(terms.updated_at),
    )


def _decision_out(decision: LegalCaseDecision | None) -> LegalDecisionOut | None:
    if decision is None:
        return None
    return LegalDecisionOut(
        status=decision.status,
        reason=decision.reason,
        condition=decision.condition,
        condition_owner=decision.condition_owner,
    )


def _out(case: LegalCase, lead: Lead) -> LegalCaseOut:
    approved = case.status == "Approved"
    return LegalCaseOut(
        id=case.id,
        lead_id=lead.id,
        hospital_name=case.hospital_name or lead.hospital_name,
        city=case.city or lead.city,
        plan=case.plan or lead.plan,
        status=case.status,
        decision_reason=case.decision_reason,
        discount=int(case.discount or 0),
        escalation=case.escalation or "Not needed",
        escalation_by=case.escalation_by,
        escalation_at=_when(case.escalation_at),
        documents=[
            LegalDocumentOut(
                id=doc.id,
                category=doc.category,
                file_name=doc.file_name,
                status=doc.status,
                uploaded_by=doc.uploaded_by,
                reviewed_by=doc.reviewed_by,
                reviewed_at=_when(doc.reviewed_at),
            )
            for doc in case.documents
        ],
        checklist=[
            ChecklistItemOut(
                id=item.id,
                label=item.label,
                status=item.status,
                note=item.note,
                updated_by=item.updated_by,
                updated_at=_when(item.updated_at),
            )
            for item in case.checklist
        ],
        finance=_finance_out(case.finance),
        decision=_decision_out(case.decision),
        advance_received=bool(case.advance_received),
        ready_to_register=approved,
    )


def _load(db: Session, case_id: int) -> tuple[LegalCase, Lead]:
    case = (
        db.query(LegalCase)
        .options(joinedload(LegalCase.documents), joinedload(LegalCase.checklist), joinedload(LegalCase.finance), joinedload(LegalCase.decision))
        .filter(LegalCase.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    lead = db.query(Lead).filter(Lead.id == case.lead_id).first()
    return case, lead


def list_cases(db: Session, actor: User) -> list[LegalCaseOut]:
    _require_reviewer(actor)
    rows = (
        db.query(LegalCase, Lead)
        .options(joinedload(LegalCase.documents), joinedload(LegalCase.checklist), joinedload(LegalCase.finance), joinedload(LegalCase.decision))
        .join(Lead, Lead.id == LegalCase.lead_id)
        .order_by(LegalCase.id.desc())
        .all()
    )
    return [_out(case, lead) for case, lead in rows]


def get_case(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    _require_reviewer(actor)
    case, lead = _load(db, case_id)
    return _out(case, lead)


def _approval_blockers(case: LegalCase) -> list[str]:
    blocked = []
    verified = [doc for doc in case.documents if doc.status == "Verified"]
    if len(case.documents) < 4 or len(verified) != len(case.documents):
        blocked.append("At least 4 documents must be uploaded and all documents verified.")
    if any(item.status not in ("Verified", "Not applicable") for item in case.checklist):
        blocked.append("Complete every legal checklist item.")
    if int(case.discount or 0) > 10 and case.escalation != "Approved":
        blocked.append("Discount above 10% requires Finance Head escalation approval.")
    return blocked


def decide_case(db: Session, actor: User, case_id: int, data: LegalDecision) -> LegalCaseOut:
    _require_reviewer(actor)
    case, lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    if data.status in ("Approved", "Conditionally Approved"):
        blocked = _approval_blockers(case)
        if blocked:
            raise HTTPException(status_code=422, detail=" ".join(blocked))
    if data.status == "Conditionally Approved" and not data.condition:
        raise HTTPException(status_code=422, detail="Enter the condition for a conditional approval.")
    if data.status == "Conditionally Approved" and not data.condition_owner:
        raise HTTPException(status_code=422, detail="Choose Accounts Team or Sales Owner for the condition.")
    case.status = data.status
    case.decision_reason = data.reason
    case.decided_by = actor.id
    case.decided_at = _now()
    if case.decision is None:
        case.decision = LegalCaseDecision(
            case_id=case.id,
            status=data.status,
            reason=data.reason,
            condition=data.condition,
            condition_owner=data.condition_owner,
            decided_by=actor.id,
            decided_at=case.decided_at,
        )
    else:
        case.decision.status = data.status
        case.decision.reason = data.reason
        case.decision.condition = data.condition
        case.decision.condition_owner = data.condition_owner
        case.decision.decided_by = actor.id
        case.decision.decided_at = case.decided_at
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def save_checklist(db: Session, actor: User, case_id: int, data: LegalChecklistUpdate) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    by_id = {item.id: item for item in case.checklist}
    for change in data.items:
        item = by_id.get(change.id)
        if item is None:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        item.status = change.status
        item.note = change.note
        item.updated_by = actor.id
        item.updated_at = _now()
    if case.status == "New from CRM":
        case.status = "In Review"
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def save_finance(db: Session, actor: User, case_id: int, data: LegalFinanceUpdate) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    terms = case.finance or LegalFinanceTerms(case_id=case.id)
    if case.finance is None:
        db.add(terms)
    terms.standard_price = data.standard_price
    terms.discount = data.discount
    terms.years = data.years
    terms.implementation_fee = data.implementation_fee
    terms.training_fee = data.training_fee
    terms.tax_percent = data.tax_percent
    terms.advance_percent = data.advance_percent
    terms.credit_days = data.credit_days
    terms.frequency = data.frequency
    terms.modules = data.modules
    terms.gstin = data.gstin
    terms.po_required = data.po_required
    terms.invoice_email = data.invoice_email
    terms.reviewed = True
    terms.updated_by = actor.id
    terms.updated_at = _now()
    case.discount = data.discount
    if data.discount > 10:
        if case.escalation not in ("Approved", "Pending"):
            case.escalation = "Not requested"
            case.escalation_by = actor.id
            case.escalation_at = terms.updated_at
    else:
        case.escalation = "Not needed"
        case.escalation_by = actor.id
        case.escalation_at = terms.updated_at
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def request_escalation(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    """Ask the Finance Head to review a discount above 10%."""
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    if int(case.discount or 0) <= 10:
        raise HTTPException(status_code=409, detail="This discount does not need Finance Head approval.")
    if case.escalation != "Not requested":
        raise HTTPException(status_code=409, detail="Escalation can be requested only while it is Not requested.")
    case.escalation = "Pending"
    case.escalation_by = actor.id
    case.escalation_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def decide_escalation(db: Session, actor: User, case_id: int, data: EscalationDecision) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if int(case.discount or 0) <= 10:
        raise HTTPException(status_code=409, detail="This discount does not need Finance Head approval.")
    if case.escalation != "Pending":
        raise HTTPException(status_code=409, detail="Request Finance Head approval before recording the decision.")
    case.escalation = data.status
    case.escalation_by = actor.id
    case.escalation_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


async def add_document(db: Session, actor: User, case_id: int, category: str, file: UploadFile) -> LegalCaseOut:
    _require_reviewer(actor)
    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(status_code=422, detail="Choose a hospital document category.")
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail="Upload a PDF, JPG, PNG, or WEBP file.")
    content = await file.read()
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="The file must be between 1 byte and 5 MB.")
    name = f"{case_id}-{uuid4().hex}{suffix}"
    path = _upload_dir() / name
    path.write_bytes(content)
    db.add(LegalDocument(
        case_id=case.id,
        category=category,
        file_name=file.filename or name,
        stored_path=str(path),
        status="Pending Review",
        uploaded_by=actor.id,
    ))
    if case.status == "New from CRM":
        case.status = "In Review"
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def _document(db: Session, case_id: int, document_id: int) -> LegalDocument:
    document = (
        db.query(LegalDocument)
        .filter(LegalDocument.id == document_id, LegalDocument.case_id == case_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def set_document_status(db: Session, actor: User, case_id: int, document_id: int, status: str) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    document = _document(db, case_id, document_id)
    document.status = status
    document.reviewed_by = actor.id
    document.reviewed_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def download_document(db: Session, actor: User, case_id: int, document_id: int) -> FileResponse:
    _require_reviewer(actor)
    document = _document(db, case_id, document_id)
    path = Path(document.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(path, filename=document.file_name)


def resubmit_case(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    """Move a case that was sent back for corrections into review again."""
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status != "Changes Requested":
        raise HTTPException(status_code=409, detail="Only a case with changes requested can be resubmitted.")
    case.status = "In Review"
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def confirm_advance(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    if _role(actor) != "accountant":
        raise HTTPException(status_code=403, detail="Only Accounts can record the advance payment")
    case, _lead = _load(db, case_id)
    if case.status != "Approved":
        raise HTTPException(status_code=409, detail="Record the advance only after Legal and Finance approves the case.")
    if case.advance_received:
        raise HTTPException(status_code=409, detail="The advance is already recorded.")
    case.advance_received = True
    case.advance_received_by = actor.id
    case.advance_received_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(case, lead)


def case_approved(db: Session, lead_id: int) -> bool:
    case = db.query(LegalCase).filter(LegalCase.lead_id == lead_id).first()
    return case is not None and case.status == "Approved"


def case_ready_for_registration(db: Session, lead_id: int) -> bool:
    case = db.query(LegalCase).filter(LegalCase.lead_id == lead_id).first()
    return case is not None and case.status == "Approved"
