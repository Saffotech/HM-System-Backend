from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from Models.lead import Lead, LeadActivity
from Models.tenant import Tenant
from Models.user import User
from Schemas.lead_schema import (
    CONTACT_METHODS,
    OPEN_STATUSES,
    LeadActivityOut,
    LeadAgree,
    LeadClose,
    LeadContact,
    LeadCreate,
    LeadDetail,
    LeadFollowUp,
    LeadNote,
    LeadSummary,
    LeadUpdate,
)
from Services import audit_service

IST = ZoneInfo("Asia/Kolkata")
CLAIM_LIMIT = 5
BLOCKED = "This lead can't be changed. It may have been reassigned or its status has changed."
EDIT_STATUSES = ("New", "Contacted", "Agreed")
CLOSE_STATUSES = ("New", "Contacted", "Agreed")
LOCKED_AFTER_AGREEMENT = ("plan", "billing_cycle")


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _person_name(user: User | None) -> str:
    if user is None:
        return ""
    return " ".join(part for part in (user.first_name, user.last_name) if part)


def _assert_platform_staff(actor: User) -> None:
    if actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="CRM leads are only available to platform staff")


def _visible(lead: Lead, actor: User) -> bool:
    if lead.assigned_to == actor.id:
        return True
    return lead.assigned_to is None and lead.status == "New"


def _contacts_visible(lead: Lead, actor: User) -> bool:
    return lead.assigned_to == actor.id


def _summary(lead: Lead, actor: User) -> LeadSummary:
    unlocked = _contacts_visible(lead, actor)
    return LeadSummary(
        id=lead.id,
        hospital_name=lead.hospital_name,
        hospital_type=lead.hospital_type,
        city=lead.city,
        state=lead.state,
        hospital_email=lead.hospital_email if unlocked else None,
        contact_person=lead.contact_person if unlocked else None,
        designation=lead.designation if unlocked else None,
        contact_phone=lead.contact_phone if unlocked else None,
        contact_email=lead.contact_email if unlocked else None,
        source=lead.source,
        priority=lead.priority,
        plan=lead.plan,
        billing_cycle=lead.billing_cycle,
        message=lead.message,
        status=lead.status,
        assigned_to=lead.assigned_to,
        created_by=lead.created_by,
        claimed_at=lead.claimed_at.isoformat() if lead.claimed_at else None,
        hospital_id=lead.hospital_id,
        registered_at=lead.registered_at.isoformat() if lead.registered_at else None,
        registered_by=lead.registered_by,
        registered_by_name=_person_name(lead.registered_by_user) or None,
        follow_up_date=lead.follow_up_date.isoformat() if lead.follow_up_date else None,
        next_action=lead.next_action if unlocked else None,
        handover_note=lead.handover_note if unlocked else None,
        agreed_at=lead.agreed_at.isoformat() if lead.agreed_at else None,
        agreed_by=lead.agreed_by,
        agreed_by_name=_person_name(lead.agreed_by_user) or None,
        close_reason=lead.close_reason,
        close_note=lead.close_note if unlocked else None,
        closed_at=lead.closed_at.isoformat() if lead.closed_at else None,
        closed_by=lead.closed_by,
        closed_by_name=_person_name(lead.closed_by_user) or None,
        contacts_visible=unlocked,
        created_at=lead.created_at.isoformat(),
        activities=_activities(lead),
    )


def _activities(lead: Lead) -> list[LeadActivityOut]:
    ordered = sorted(lead.activities, key=lambda item: (item.created_at, item.id), reverse=True)
    return [
        LeadActivityOut(
            id=item.id,
            at=item.created_at.isoformat(),
            actor_id=item.actor_id,
            actor_name=_person_name(item.actor),
            method=item.method,
            note=item.note or "",
            follow_up_date=item.follow_up_date.isoformat() if item.follow_up_date else None,
            next_action=item.next_action,
        )
        for item in ordered
    ]


def _detail(lead: Lead, actor: User) -> LeadDetail:
    return LeadDetail(**_summary(lead, actor).model_dump())


def _lead_query(db: Session):
    return db.query(Lead).options(
        selectinload(Lead.activities).joinedload(LeadActivity.actor),
        joinedload(Lead.creator),
        joinedload(Lead.assignee),
        joinedload(Lead.agreed_by_user),
        joinedload(Lead.closed_by_user),
        joinedload(Lead.registered_by_user),
    )


def _find_duplicates(db: Session, data: LeadCreate, actor: User) -> list[dict]:
    name = data.hospital_name.casefold()
    email = str(data.contact_email).casefold() if data.contact_email else ""
    phone = _digits(data.contact_phone)
    matches: list[dict] = []

    for lead in db.query(Lead).all():
        reasons = []
        if lead.hospital_name.strip().casefold() == name:
            reasons.append("Same hospital name")
        lead_emails = {
            item.casefold()
            for item in (lead.contact_email, lead.hospital_email)
            if item
        }
        if email and email in lead_emails:
            reasons.append("Same email")
        if phone and _digits(lead.contact_phone) == phone:
            reasons.append("Same phone")
        if not reasons:
            continue
        mine = lead.assigned_to == actor.id
        unclaimed = lead.assigned_to is None and lead.status == "New"
        matches.append({
            "kind": "lead",
            "id": lead.id if mine or unclaimed else None,
            "visibility": "mine" if mine else "unclaimed" if unclaimed else "hidden",
            "name": lead.hospital_name if mine or unclaimed else None,
            "status": lead.status if mine or unclaimed else None,
            "reasons": reasons,
        })

    for hospital in db.query(Tenant).all():
        reasons = []
        if hospital.name and hospital.name.strip().casefold() == name:
            reasons.append("Same hospital name")
        if email and hospital.email and hospital.email.strip().casefold() == email:
            reasons.append("Same email")
        if phone and _digits(hospital.phone) == phone:
            reasons.append("Same phone")
        if not reasons:
            continue
        matches.append({
            "kind": "hospital",
            "id": hospital.id,
            "name": hospital.name,
            "city": hospital.city,
            "reasons": reasons,
        })
    return matches


def create_lead(db: Session, data: LeadCreate, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    matches = _find_duplicates(db, data, actor)
    if matches and not data.allow_duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This hospital matches an existing lead or a hospital that is already registered.",
                "matches": matches,
            },
        )

    lead = Lead(
        hospital_name=data.hospital_name,
        hospital_type=data.hospital_type,
        city=data.city,
        state=data.state,
        contact_person=data.contact_person,
        designation=data.designation,
        contact_phone=data.contact_phone,
        contact_email=str(data.contact_email).lower() if data.contact_email else None,
        source=data.source,
        priority=data.priority,
        plan=data.plan,
        billing_cycle=data.billing_cycle,
        message=data.message,
        status="New",
        assigned_to=None if data.shared else actor.id,
        created_by=actor.id,
    )
    db.add(lead)
    db.flush()
    note = f"Source: {data.source}."
    if data.shared:
        note = f"{note} Shared in New enquiries for any CRM employee to claim."
    db.add(LeadActivity(lead_id=lead.id, actor_id=actor.id, method="Lead created", note=note))
    audit_service.log_event(
        db,
        actor=actor,
        action="lead.create",
        resource_type="lead",
        resource_id=lead.id,
        summary=f"Created lead {lead.hospital_name}",
        details={"shared": data.shared, "source": data.source},
    )
    saved = _lead_query(db).filter(Lead.id == lead.id).one()
    return _detail(saved, actor)


def list_leads(db: Session, actor: User) -> list[LeadSummary]:
    _assert_platform_staff(actor)
    leads = (
        db.query(Lead)
        .options(
            selectinload(Lead.activities).joinedload(LeadActivity.actor),
            joinedload(Lead.agreed_by_user),
            joinedload(Lead.closed_by_user),
            joinedload(Lead.registered_by_user),
        )
        .filter(
            (Lead.assigned_to == actor.id)
            | ((Lead.assigned_to.is_(None)) & (Lead.status == "New"))
        )
        .order_by(Lead.created_at.desc())
        .all()
    )
    return [_summary(lead, actor) for lead in leads]


def get_lead(db: Session, lead_id: int, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _lead_query(db).filter(Lead.id == lead_id).first()
    if lead is None or not _visible(lead, actor):
        raise HTTPException(status_code=404, detail="Lead not found")
    return _detail(lead, actor)


def _today():
    return datetime.now(IST).date()


def _lock_lead(db: Session, lead_id: int) -> Lead | None:
    return db.query(Lead).filter(Lead.id == lead_id).with_for_update().first()


def _require_owner(lead: Lead | None, actor: User, statuses: tuple[str, ...] | None) -> Lead:
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.assigned_to is None and lead.status == "New":
        raise HTTPException(status_code=409, detail="Claim this lead before changing it.")
    if lead.assigned_to != actor.id:
        raise HTTPException(status_code=404, detail="Lead not found")
    if statuses is not None and lead.status not in statuses:
        raise HTTPException(status_code=409, detail=BLOCKED)
    return lead


def _activity(
    db: Session,
    lead: Lead,
    actor: User,
    method: str,
    note: str,
    follow_up_date=None,
    next_action: str | None = None,
) -> None:
    db.add(LeadActivity(
        lead_id=lead.id,
        actor_id=actor.id,
        method=method,
        note=note,
        follow_up_date=follow_up_date,
        next_action=next_action,
    ))


def _save(db: Session, lead: Lead, actor: User, action: str, summary: str, details: dict | None = None) -> LeadDetail:
    audit_service.log_event(
        db,
        actor=actor,
        action=action,
        resource_type="lead",
        resource_id=lead.id,
        summary=summary,
        details=details,
    )
    saved = _lead_query(db).filter(Lead.id == lead.id).one()
    return _detail(saved, actor)


def _ensure_future_date(value) -> None:
    if value < _today():
        raise HTTPException(status_code=422, detail="The follow-up date can't be in the past.")


def claim_lead(db: Session, lead_id: int, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    # Lock the caller first so two of their own claims cannot both pass the limit of 5.
    db.query(User).filter(User.id == actor.id).with_for_update().one()
    lead = _lock_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.assigned_to == actor.id:
        return _detail(_lead_query(db).filter(Lead.id == lead.id).one(), actor)
    if lead.assigned_to is not None:
        raise HTTPException(status_code=409, detail="This lead has already been claimed.")
    if lead.status != "New":
        raise HTTPException(status_code=404, detail="Lead not found")

    uncontacted = (
        db.query(func.count(Lead.id))
        .filter(Lead.assigned_to == actor.id, Lead.status == "New")
        .scalar()
    )
    if uncontacted >= CLAIM_LIMIT:
        raise HTTPException(
            status_code=409,
            detail=(
                f"You already have {CLAIM_LIMIT} new leads you haven't contacted. "
                "Contact one of them before claiming more."
            ),
        )

    lead.assigned_to = actor.id
    lead.claimed_at = datetime.now(IST)
    _activity(db, lead, actor, "Claimed", "Claimed from New enquiries.")
    return _save(
        db,
        lead,
        actor,
        "lead.claim",
        f"Claimed lead {lead.hospital_name}",
        {"lead_id": lead.id},
    )


def log_contact(db: Session, lead_id: int, data: LeadContact, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, OPEN_STATUSES)
    if data.outcome in ("interested", "callback"):
        _ensure_future_date(data.follow_up_date)

    became_contacted = lead.status == "New"
    if data.outcome == "not-interested":
        lead.status = "Not Interested"
        lead.close_reason = data.reason
        lead.close_note = data.note
        lead.closed_by = actor.id
        lead.closed_at = datetime.now(IST)
        lead.follow_up_date = None
        lead.next_action = None
        _activity(db, lead, actor, data.method, data.note)
        _activity(db, lead, actor, "Closed", data.reason)
        action = "lead.close"
        summary = f"Closed lead {lead.hospital_name}"
    else:
        if became_contacted:
            lead.status = "Contacted"
        if data.outcome == "agreed":
            lead.follow_up_date = None
            lead.next_action = None
        else:
            lead.follow_up_date = data.follow_up_date
            lead.next_action = data.next_action
        _activity(
            db,
            lead,
            actor,
            data.method,
            data.note,
            follow_up_date=None if data.outcome == "agreed" else data.follow_up_date,
            next_action=None if data.outcome == "agreed" else data.next_action,
        )
        action = "lead.contact"
        summary = f"Logged contact for {lead.hospital_name}"

    return _save(
        db,
        lead,
        actor,
        action,
        summary,
        {"outcome": data.outcome, "method": data.method, "status": lead.status},
    )


def schedule_follow_up(db: Session, lead_id: int, data: LeadFollowUp, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, OPEN_STATUSES)
    _ensure_future_date(data.follow_up_date)
    same_date = lead.follow_up_date == data.follow_up_date
    same_action = (lead.next_action or "") == (data.next_action or "")
    if lead.follow_up_date is not None and same_date and same_action:
        raise HTTPException(status_code=422, detail="Pick a different date or next action.")

    if lead.follow_up_date is not None:
        method = "Follow-up rescheduled"
        summary_note = f"Moved from {lead.follow_up_date.isoformat()} to {data.follow_up_date.isoformat()}."
    else:
        method = "Follow-up scheduled"
        summary_note = f"Follow-up set for {data.follow_up_date.isoformat()}."
    note = f"{summary_note} {data.note}" if data.note else summary_note
    lead.follow_up_date = data.follow_up_date
    lead.next_action = data.next_action
    _activity(db, lead, actor, method, note, data.follow_up_date, data.next_action)
    return _save(
        db,
        lead,
        actor,
        "lead.follow_up",
        f"Scheduled follow-up for {lead.hospital_name}",
        {"follow_up_date": data.follow_up_date.isoformat()},
    )


def add_note(db: Session, lead_id: int, data: LeadNote, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, None)
    if lead.status == "Registered":
        raise HTTPException(status_code=409, detail="Registered leads are read-only.")
    _activity(db, lead, actor, "Note", data.note)
    return _save(db, lead, actor, "lead.note", f"Added a note on {lead.hospital_name}")


_EDIT_LABELS = {
    "priority": "priority",
    "source": "source",
    "hospital_type": "hospital type",
    "contact_person": "contact person",
    "designation": "designation",
    "contact_phone": "phone",
    "contact_email": "contact email",
    "hospital_email": "hospital email",
    "city": "city",
    "state": "state",
    "plan": "plan",
    "billing_cycle": "billing cycle",
}


def update_lead(db: Session, lead_id: int, data: LeadUpdate, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, EDIT_STATUSES)
    changes: list[str] = []
    for field, label in _EDIT_LABELS.items():
        if field not in data.model_fields_set:
            continue
        value = getattr(data, field)
        if field in ("contact_email", "hospital_email") and value is not None:
            value = str(value).lower()
        current = getattr(lead, field)
        if lead.status == "Agreed" and field in LOCKED_AFTER_AGREEMENT and (current or "") != (value or ""):
            raise HTTPException(status_code=409, detail="Plan and billing cycle are locked after the hospital agrees.")
        if field in ("contact_person", "contact_phone", "city") and not value:
            raise HTTPException(status_code=422, detail=f"Enter the {label}.")
        if (current or "") == (value or ""):
            continue
        setattr(lead, field, value)
        changes.append(label)

    if not changes:
        return _detail(_lead_query(db).filter(Lead.id == lead.id).one(), actor)

    _activity(db, lead, actor, "Details updated", f"Updated {', '.join(changes)}.")
    return _save(
        db,
        lead,
        actor,
        "lead.update",
        f"Updated lead {lead.hospital_name}",
        {"fields": changes},
    )


def agree_lead(db: Session, lead_id: int, data: LeadAgree, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, ("Contacted",))
    lead.status = "Agreed"
    lead.plan = data.plan
    lead.billing_cycle = data.billing_cycle
    lead.handover_note = data.note
    lead.agreed_at = datetime.now(IST)
    lead.agreed_by = actor.id
    lead.follow_up_date = None
    lead.next_action = None
    note = f"Hospital agreed to register on {data.plan} · {data.billing_cycle}. Sent to accounts."
    if data.note:
        note = f"{note} {data.note}"
    _activity(db, lead, actor, "Agreed", note)
    return _save(
        db,
        lead,
        actor,
        "lead.agree",
        f"Sent {lead.hospital_name} to Accounts",
        {"plan": data.plan, "billing_cycle": data.billing_cycle},
    )


def close_lead(db: Session, lead_id: int, data: LeadClose, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, CLOSE_STATUSES)
    previous_status = lead.status
    lead.status = "Not Interested"
    lead.close_reason = data.reason
    lead.close_note = data.note
    lead.closed_by = actor.id
    lead.closed_at = datetime.now(IST)
    lead.follow_up_date = None
    lead.next_action = None
    note = f"{data.reason}. {data.note}" if data.note else data.reason
    _activity(db, lead, actor, "Closed", note)
    return _save(
        db,
        lead,
        actor,
        "lead.close",
        f"Closed lead {lead.hospital_name}",
        {"reason": data.reason, "previous_status": previous_status},
    )


def reopen_lead(db: Session, lead_id: int, actor: User) -> LeadDetail:
    _assert_platform_staff(actor)
    lead = _require_owner(_lock_lead(db, lead_id), actor, ("Not Interested",))
    had_contact = (
        db.query(LeadActivity.id)
        .filter(LeadActivity.lead_id == lead.id, LeadActivity.method.in_(CONTACT_METHODS))
        .first()
    )
    lead.status = "Contacted" if had_contact else "New"
    lead.close_reason = None
    lead.close_note = None
    lead.closed_by = None
    lead.closed_at = None
    _activity(db, lead, actor, "Reopened", "Request reopened for follow-up.")
    return _save(
        db,
        lead,
        actor,
        "lead.reopen",
        f"Reopened lead {lead.hospital_name}",
        {"status": lead.status},
    )
