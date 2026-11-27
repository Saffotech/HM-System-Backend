"""Legal and Finance sits between an agreed CRM lead and hospital registration."""
import os
from datetime import datetime
from pathlib import Path, PurePath
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from Models.lead import Lead
from Models.legal_case import LegalCase, LegalCaseDecision, LegalChecklistItem, LegalDocument, LegalFinanceTerms
from Models.user import User
from Services.plan_service import price_for
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

# A document category and the checklist row that reviews it stay on the same status.
CATEGORY_CHECKLIST = {
    "Hospital Registration": "Hospital registration documents reviewed",
    "Entity Registration": "Legal entity identity verified",
    "Authorized Representative": "Authorized signatory verified",
    "Hospital License": "Relevant licenses checked (where applicable)",
    "Service Agreement": "Agreement and data protection terms reviewed",
}
CHECKLIST_CATEGORY = {label: category for category, label in CATEGORY_CHECKLIST.items()}
DOCUMENT_STATUS_FOR_CHECKLIST = {
    "Verified": "Verified",
    "Pending": "Pending Review",
    "Issue Found": "Changes Requested",
}


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


DECIDED = ("Approved", "Rejected", "Conditionally Approved")


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return name or None


def _user_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return _full_name(db.query(User).filter(User.id == user_id).first())


def _copy_snapshot(db: Session, case: LegalCase, lead: Lead) -> None:
    case.hospital_name = lead.hospital_name
    case.city = lead.city
    case.plan = lead.plan
    case.hospital_type = lead.hospital_type
    case.state = lead.state
    case.hospital_email = lead.hospital_email
    case.contact_person = lead.contact_person
    case.designation = lead.designation
    case.contact_phone = lead.contact_phone
    case.contact_email = lead.contact_email
    case.lead_source = lead.source
    case.priority = lead.priority
    case.requirement = lead.message
    case.assigned_employee_id = lead.assigned_to
    case.assigned_employee_name = _user_name(db, lead.assigned_to)
    case.agreed_at = lead.agreed_at
    case.agreed_by_name = _user_name(db, lead.agreed_by)
    case.handover_note = lead.handover_note
    case.billing_cycle = lead.billing_cycle


def _change_note(old_plan, new_plan, old_cycle, new_cycle) -> str:
    parts = []
    if (old_plan or "") != (new_plan or ""):
        parts.append(f"plan changed from {old_plan or 'none'} to {new_plan or 'none'}")
    if (old_cycle or "") != (new_cycle or ""):
        parts.append(f"billing cycle changed from {old_cycle or 'none'} to {new_cycle or 'none'}")
    return "Finance review required. " + "; ".join(parts) + "."


def _apply_finance(db: Session, case: LegalCase, lead: Lead, old_plan: str | None, old_cycle: str | None) -> bool:
    """Return True when a reviewed price must be reviewed again."""
    price = price_for(db, lead.plan, lead.billing_cycle)
    terms = case.finance
    if terms is None:
        terms = LegalFinanceTerms(
            case_id=case.id,
            frequency=lead.billing_cycle,
            standard_price=price,
            reviewed=False,
            invoice_email=None,
        )
        db.add(terms)
        case.finance = terms
        return False
    if not terms.reviewed:
        terms.frequency = lead.billing_cycle
        terms.standard_price = price
        return False
    if (old_plan or "") == (lead.plan or "") and (old_cycle or "") == (lead.billing_cycle or ""):
        return False
    previous_price = price_for(db, old_plan, old_cycle) if old_plan and old_cycle else None
    terms.frequency = lead.billing_cycle
    if terms.standard_price == 0 or (previous_price is not None and terms.standard_price == previous_price):
        terms.standard_price = price
    terms.reviewed = False
    case.commercial_change_note = _change_note(old_plan, lead.plan, old_cycle, lead.billing_cycle)
    return True


def sync_case_from_lead(db: Session, lead: Lead) -> None:
    """Copy CRM edits onto the case. Plan and billing stay on the agreement path."""
    existing = (
        db.query(LegalCase)
        .options(joinedload(LegalCase.finance))
        .filter(LegalCase.lead_id == lead.id)
        .first()
    )
    if existing is None:
        return
    if existing.status in DECIDED:
        existing.city = lead.city
        existing.state = lead.state
        existing.hospital_type = lead.hospital_type
        existing.hospital_email = lead.hospital_email
        existing.contact_person = lead.contact_person
        existing.designation = lead.designation
        existing.contact_phone = lead.contact_phone
        existing.contact_email = lead.contact_email
        existing.lead_source = lead.source
        existing.priority = lead.priority
        db.flush()
        return
    open_case_for_agreed_lead(db, lead)


def open_case_for_agreed_lead(db: Session, lead: Lead) -> LegalCase:
    """One agreed hospital lead gets one case. A second call updates the same row."""
    existing = (
        db.query(LegalCase)
        .options(joinedload(LegalCase.finance))
        .filter(LegalCase.lead_id == lead.id)
        .first()
    )
    if existing is not None:
        existing.finance_rereview_required = False
        if existing.status in DECIDED:
            return existing
        old_plan = existing.plan
        old_cycle = existing.billing_cycle
        _copy_snapshot(db, existing, lead)
        existing.finance_rereview_required = _apply_finance(db, existing, lead, old_plan, old_cycle)
        db.flush()
        return existing
    case = LegalCase(
        lead_id=lead.id,
        status="New from CRM",
        advance_received=False,
        discount=0,
    )
    _copy_snapshot(db, case, lead)
    db.add(case)
    db.flush()
    for label in HOSPITAL_CHECKLIST:
        db.add(LegalChecklistItem(case_id=case.id, label=label, status="Pending"))
    price = price_for(db, lead.plan, lead.billing_cycle)
    db.add(LegalFinanceTerms(
        case_id=case.id,
        frequency=lead.billing_cycle,
        standard_price=price,
        reviewed=False,
        invoice_email=None,
    ))
    case.finance_rereview_required = False
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


def _person_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return name or None


def _display_file_name(value: str | None) -> str:
    name = PurePath(str(value or "").replace("\\", "/")).name.strip()
    return name or "Document"


def _unique_rows(rows):
    seen = set()
    unique = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        unique.append(row)
    return unique


def _uploader_names(db: Session, documents) -> dict[int, str]:
    ids = {doc.uploaded_by for doc in documents if doc.uploaded_by is not None}
    if not ids:
        return {}
    rows = db.query(User).filter(User.id.in_(ids)).all()
    return {row.id: name for row in rows if (name := _person_name(row))}


def _checklist_status_for_documents(documents) -> str | None:
    if not documents:
        return None
    if any(doc.status == "Changes Requested" for doc in documents):
        return "Issue Found"
    if any(doc.status != "Verified" for doc in documents):
        return "Pending"
    return "Verified"


def _set_checklist_status(item: LegalChecklistItem, status: str, actor: User) -> None:
    if item.status == status:
        return
    item.status = status
    item.updated_by = actor.id
    item.updated_at = _now()


def _sync_checklist_from_documents(case: LegalCase, actor: User, categories: set[str]) -> None:
    """A document upload or review moves the matching checklist row with it."""
    by_label = {item.label: item for item in case.checklist}
    for category in categories:
        item = by_label.get(CATEGORY_CHECKLIST.get(category, ""))
        if item is None:
            continue
        status = _checklist_status_for_documents(
            [doc for doc in case.documents if doc.category == category]
        )
        if status:
            _set_checklist_status(item, status, actor)


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value


def _reconcile_linked_reviews(case: LegalCase, actor: User) -> bool:
    """Make a document category and its checklist row agree, keeping the later change."""
    changed = False
    by_label = {item.label: item for item in case.checklist}
    for category, label in CATEGORY_CHECKLIST.items():
        item = by_label.get(label)
        docs = [doc for doc in case.documents if doc.category == category]
        if item is None or not docs:
            continue
        from_docs = _checklist_status_for_documents(docs)
        if item.status == from_docs:
            continue
        latest_doc = max(
            (_as_utc(doc.reviewed_at or doc.created_at) for doc in docs),
            default=None,
        )
        checklist_at = _as_utc(item.updated_at)
        documents_are_newer = latest_doc is not None and (
            checklist_at is None or latest_doc >= checklist_at
        )
        if documents_are_newer:
            _set_checklist_status(item, from_docs, actor)
            changed = True
            continue
        document_status = DOCUMENT_STATUS_FOR_CHECKLIST.get(item.status)
        if not document_status:
            continue
        now = _now()
        for doc in docs:
            if doc.status == document_status:
                continue
            doc.status = document_status
            doc.reviewed_by = actor.id
            doc.reviewed_at = now
            changed = True
    return changed


def _sync_documents_from_checklist(case: LegalCase, actor: User, labels: set[str]) -> None:
    """A checklist change moves every document in that category with it."""
    now = _now()
    for label in labels:
        category = CHECKLIST_CATEGORY.get(label)
        if not category:
            continue
        item = next((row for row in case.checklist if row.label == label), None)
        document_status = DOCUMENT_STATUS_FOR_CHECKLIST.get(item.status) if item is not None else None
        if not document_status:
            continue
        for doc in case.documents:
            if doc.category != category or doc.status == document_status:
                continue
            doc.status = document_status
            doc.reviewed_by = actor.id
            doc.reviewed_at = now


def _kept(stored, live):
    return live if stored is None else stored


def _refresh_crm_details(case: LegalCase, lead: Lead) -> bool:
    """Keep hospital contact details aligned with the CRM lead."""
    fields = {
        "city": lead.city,
        "state": lead.state,
        "hospital_type": lead.hospital_type,
        "hospital_email": lead.hospital_email,
        "contact_person": lead.contact_person,
        "designation": lead.designation,
        "contact_phone": lead.contact_phone,
        "contact_email": lead.contact_email,
        "lead_source": lead.source,
        "priority": lead.priority,
    }
    changed = False
    for name, value in fields.items():
        if getattr(case, name) != value:
            setattr(case, name, value)
            changed = True
    return changed


def _out(db: Session, case: LegalCase, lead: Lead) -> LegalCaseOut:
    documents = _unique_rows(case.documents)
    checklist = _unique_rows(case.checklist)
    names = _uploader_names(db, documents)
    return LegalCaseOut(
        id=case.id,
        lead_id=lead.id,
        hospital_name=_kept(case.hospital_name, lead.hospital_name),
        city=lead.city,
        plan=_kept(case.plan, lead.plan),
        hospital_type=lead.hospital_type,
        state=lead.state,
        hospital_email=lead.hospital_email,
        contact_person=lead.contact_person,
        designation=lead.designation,
        contact_phone=lead.contact_phone,
        contact_email=lead.contact_email,
        lead_source=lead.source,
        priority=lead.priority,
        requirement=_kept(case.requirement, lead.message),
        assigned_employee_id=_kept(case.assigned_employee_id, lead.assigned_to),
        assigned_employee_name=_kept(case.assigned_employee_name, _full_name(getattr(lead, "assignee", None))),
        agreed_at=_when(_kept(case.agreed_at, lead.agreed_at)),
        agreed_by_name=case.agreed_by_name,
        handover_note=_kept(case.handover_note, lead.handover_note),
        billing_cycle=_kept(case.billing_cycle, lead.billing_cycle),
        commercial_change_note=case.commercial_change_note,
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
                file_name=_display_file_name(doc.file_name),
                status=doc.status,
                uploaded_by=doc.uploaded_by,
                uploaded_by_name=names.get(doc.uploaded_by),
                uploaded_at=_when(doc.created_at),
                reviewed_by=doc.reviewed_by,
                reviewed_at=_when(doc.reviewed_at),
            )
            for doc in documents
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
            for item in checklist
        ],
        finance=_finance_out(case.finance),
        decision=_decision_out(case.decision),
        advance_received=bool(case.advance_received),
        ready_to_register=approvals_complete(case),
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
    seen = set()
    pairs = []
    changed = False
    for case, lead in rows:
        if case.id in seen:
            continue
        seen.add(case.id)
        changed = _refresh_crm_details(case, lead) or changed
        changed = _reconcile_linked_reviews(case, actor) or changed
        pairs.append((case, lead))
    if changed:
        db.commit()
    return [_out(db, case, lead) for case, lead in pairs]


def get_case(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    _require_reviewer(actor)
    case, lead = _load(db, case_id)
    changed = _refresh_crm_details(case, lead)
    if _reconcile_linked_reviews(case, actor) or changed:
        db.commit()
        case, lead = _load(db, case_id)
    return _out(db, case, lead)


def approvals_complete(case: LegalCase | None) -> bool:
    """Legal Docs and Finance are both finished, including a required escalation.

    A missing case or finance row is incomplete. It is not an error.
    """
    if case is None or case.status != "Approved":
        return False
    terms = case.finance
    if terms is None or not terms.reviewed:
        return False
    if int(case.discount or 0) > 10 and case.escalation != "Approved":
        return False
    return True


def _commercial_terms_locked(case: LegalCase) -> bool:
    """Reviewed terms stay fixed once Legal has approved them.

    A CRM commercial change clears the review, so Finance can approve again.
    """
    if case.status not in ("Approved", "Conditionally Approved"):
        return False
    terms = case.finance
    if terms is None or not terms.reviewed:
        return False
    return not case.commercial_change_note


def _approval_blockers(case: LegalCase) -> list[str]:
    blocked = []
    current_documents = [doc for doc in case.documents if getattr(doc, "is_current", True)]
    verified = [doc for doc in current_documents if doc.status == "Verified"]
    if len(current_documents) < 4 or len(verified) != len(current_documents):
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
    return _out(db, case, lead)


def save_checklist(db: Session, actor: User, case_id: int, data: LegalChecklistUpdate) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    by_id = {item.id: item for item in case.checklist}
    changed_labels = set()
    for change in data.items:
        item = by_id.get(change.id)
        if item is None:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        item.status = change.status
        item.note = change.note
        item.updated_by = actor.id
        item.updated_at = _now()
        changed_labels.add(item.label)
    _sync_documents_from_checklist(case, actor, changed_labels)
    if case.status == "New from CRM":
        case.status = "In Review"
    db.commit()
    case, lead = _load(db, case_id)
    return _out(db, case, lead)


def save_finance(db: Session, actor: User, case_id: int, data: LegalFinanceUpdate) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status == "Rejected":
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    if _commercial_terms_locked(case):
        raise HTTPException(status_code=409, detail="Approved commercial terms cannot be changed.")
    if case.status in ("Approved", "Conditionally Approved") and data.discount > 10 and case.escalation != "Approved":
        raise HTTPException(status_code=422, detail="Discount above 10% requires Finance Head escalation approval.")
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
    case.commercial_change_note = None
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
    return _out(db, case, lead)


def request_escalation(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    """Ask the Finance Head to review a discount above 10%."""
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status == "Rejected" or _commercial_terms_locked(case):
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
    return _out(db, case, lead)


def decide_escalation(db: Session, actor: User, case_id: int, data: EscalationDecision) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status == "Rejected" or _commercial_terms_locked(case):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    if int(case.discount or 0) <= 10:
        raise HTTPException(status_code=409, detail="This discount does not need Finance Head approval.")
    if case.escalation != "Pending":
        raise HTTPException(status_code=409, detail="Request Finance Head approval before recording the decision.")
    case.escalation = data.status
    case.escalation_by = actor.id
    case.escalation_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(db, case, lead)


def _category_allowed(db: Session, category: str) -> bool:
    if category in DOCUMENT_CATEGORIES:
        return True
    try:
        from client_documents.Services.document_type_service import by_name
        return by_name(db, category) is not None
    except Exception:
        return False


async def add_document(db: Session, actor: User, case_id: int, category: str, file: UploadFile) -> LegalCaseOut:
    _require_reviewer(actor)
    if not _category_allowed(db, category):
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
    from client_documents.Services.document_storage_service import save_private
    path = save_private(case.id, suffix, content)
    original = PurePath((file.filename or "").replace("\\", "/")).name.strip()
    db.add(LegalDocument(
        case_id=case.id,
        category=category,
        file_name=original or path.name,
        stored_path=str(path),
        status="Pending Review",
        uploaded_by=actor.id,
        upload_source="EMPLOYEE",
        is_current=True,
        version=1,
    ))
    if case.status == "New from CRM":
        case.status = "In Review"
    db.flush()
    db.expire(case, ["documents"])
    _sync_checklist_from_documents(case, actor, {category})
    db.commit()
    case, lead = _load(db, case_id)
    return _out(db, case, lead)


def _document(db: Session, case_id: int, document_id: int) -> LegalDocument:
    document = (
        db.query(LegalDocument)
        .filter(LegalDocument.id == document_id, LegalDocument.case_id == case_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def set_document_status(db: Session, actor: User, case_id: int, document_id: int, status: str, remarks: str | None = None) -> LegalCaseOut:
    _require_reviewer(actor)
    case, _lead = _load(db, case_id)
    if case.status in ("Approved", "Rejected", "Conditionally Approved"):
        raise HTTPException(status_code=409, detail="This case already has a decision.")
    document = _document(db, case_id, document_id)
    from client_documents.Services.document_review_service import record_review
    record_review(db, actor, document, status, remarks)
    document.status = status
    document.reviewed_by = actor.id
    document.reviewed_at = _now()
    _sync_checklist_from_documents(case, actor, {document.category})
    db.commit()
    case, lead = _load(db, case_id)
    return _out(db, case, lead)


def download_document(db: Session, actor: User, case_id: int, document_id: int) -> FileResponse:
    _require_reviewer(actor)
    document = _document(db, case_id, document_id)
    from client_documents.Services.document_storage_service import StorageError, resolve_existing
    try:
        path = resolve_existing(document.stored_path)
    except StorageError:
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
    return _out(db, case, lead)


def confirm_advance(db: Session, actor: User, case_id: int) -> LegalCaseOut:
    if _role(actor) != "accountant":
        raise HTTPException(status_code=403, detail="Only Accounts can record the advance payment")
    case, _lead = _load(db, case_id)
    if not approvals_complete(case):
        raise HTTPException(status_code=409, detail="Record the advance only after Legal and Finance approves the case.")
    if case.advance_received:
        raise HTTPException(status_code=409, detail="The advance is already recorded.")
    case.advance_received = True
    case.advance_received_by = actor.id
    case.advance_received_at = _now()
    db.commit()
    case, lead = _load(db, case_id)
    return _out(db, case, lead)


def case_approved(db: Session, lead_id: int) -> bool:
    """Legal Docs decision only. Registration uses case_ready_for_registration."""
    case = db.query(LegalCase).filter(LegalCase.lead_id == lead_id).first()
    return case is not None and case.status == "Approved"


def case_ready_for_registration(db: Session, lead_id: int) -> bool:
    case = (
        db.query(LegalCase)
        .options(joinedload(LegalCase.finance))
        .filter(LegalCase.lead_id == lead_id)
        .first()
    )
    return approvals_complete(case)
