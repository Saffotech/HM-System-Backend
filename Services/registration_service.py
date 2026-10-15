from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.lead import Lead, LeadActivity
from Models.tenant import Tenant
from Models.user import User
from Schemas.registration_schema import RegisterFromLead, RegistrationOut
from Schemas.tenant_schema import TenantRegisterRequest
from Services import audit_service
from Services.tenant_service import register_tenant

IST = ZoneInfo("Asia/Kolkata")
QUEUE_STATUSES = {"agreed": "Agreed", "registered": "Registered"}


def _assert_accountant(actor: User) -> None:
    if actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Hospital registration is only available to platform staff")


def _person_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return name or None


def _load(db: Session, lead_id: int) -> Lead | None:
    return (
        db.query(Lead)
        .options(
            joinedload(Lead.agreed_by_user),
            joinedload(Lead.registered_by_user),
        )
        .filter(Lead.id == lead_id)
        .first()
    )


def _out(lead: Lead, hospital_code: str | None = None) -> RegistrationOut:
    return RegistrationOut(
        id=lead.id,
        hospital_name=lead.hospital_name,
        hospital_type=lead.hospital_type,
        city=lead.city,
        state=lead.state,
        hospital_email=lead.hospital_email,
        contact_person=lead.contact_person,
        designation=lead.designation,
        contact_phone=lead.contact_phone,
        contact_email=lead.contact_email,
        plan=lead.plan,
        billing_cycle=lead.billing_cycle,
        source=lead.source,
        agreed_at=lead.agreed_at.isoformat() if lead.agreed_at else None,
        agreed_by_name=_person_name(lead.agreed_by_user),
        handover_note=lead.handover_note,
        status=lead.status,
        hospital_id=lead.hospital_id,
        hospital_code=hospital_code,
        registered_at=lead.registered_at.isoformat() if lead.registered_at else None,
        registered_by_name=_person_name(lead.registered_by_user),
    )


def list_registrations(db: Session, actor: User, status: str) -> list[RegistrationOut]:
    _assert_accountant(actor)
    lead_status = QUEUE_STATUSES.get(status)
    if lead_status is None:
        raise HTTPException(status_code=422, detail="Status must be agreed or registered.")
    leads = (
        db.query(Lead)
        .options(joinedload(Lead.agreed_by_user), joinedload(Lead.registered_by_user))
        .filter(Lead.status == lead_status)
        .order_by(Lead.agreed_at.asc() if lead_status == "Agreed" else Lead.registered_at.desc())
        .all()
    )
    return [_out(lead) for lead in leads]


def get_registration(db: Session, actor: User, lead_id: int) -> RegistrationOut:
    _assert_accountant(actor)
    lead = _load(db, lead_id)
    if lead is None or lead.status not in ("Agreed", "Registered"):
        raise HTTPException(status_code=404, detail="Registration not found")
    code = None
    if lead.hospital_id is not None:
        hospital = db.query(Tenant).filter(Tenant.id == lead.hospital_id).first()
        code = hospital.code if hospital else None
    return _out(lead, code)


def register_from_lead(db: Session, actor: User, lead_id: int, data: RegisterFromLead) -> RegistrationOut:
    _assert_accountant(actor)
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id)
        .with_for_update()
        .first()
    )
    if lead is None or lead.status not in ("Agreed", "Registered"):
        raise HTTPException(status_code=404, detail="Registration not found")
    if lead.status != "Agreed" or lead.hospital_id is not None:
        raise HTTPException(status_code=409, detail="This hospital is already registered.")
    if not lead.contact_email:
        raise HTTPException(status_code=422, detail="Contact email is required on the lead before it can be registered.")
    if not (lead.state or "").strip():
        raise HTTPException(status_code=422, detail="State is required on the lead before it can be registered.")

    hospital_email = (lead.hospital_email or lead.contact_email).strip().lower()
    created = register_tenant(
        db,
        TenantRegisterRequest(
            name=lead.hospital_name,
            code=data.code,
            hospital_type=lead.hospital_type,
            email=hospital_email,
            phone=lead.contact_phone,
            address=data.address,
            city=lead.city,
            state=lead.state,
            pincode=data.pincode,
            admin_full_name=lead.contact_person,
            admin_email=lead.contact_email,
            admin_phone=lead.contact_phone,
            admin_password=data.admin_password,
            plan=data.plan,
            billing_cycle=data.billing_cycle,
            trial_period=data.trial_period,
            tenant_status=data.tenant_status,
        ),
        actor,
        commit=False,
    )

    lead.status = "Registered"
    lead.hospital_id = created.tenant_id
    lead.registered_by = actor.id
    lead.registered_at = datetime.now(IST)
    lead.follow_up_date = None
    lead.next_action = None
    db.add(LeadActivity(
        lead_id=lead.id,
        actor_id=actor.id,
        method="Registration",
        note=f"Registered as hospital {created.tenant_id} ({created.code}).",
    ))
    audit_service.log_event(
        db,
        actor=actor,
        action="lead.register",
        resource_type="lead",
        resource_id=lead.id,
        summary=f"Registered {lead.hospital_name} as hospital {created.code}",
        details={
            "tenant_id": created.tenant_id,
            "code": created.code,
            "admin_email": created.admin_email,
            "admin_user_id": created.admin_user_id,
            "plan": created.plan,
            "billing_cycle": created.billing_cycle,
            "trial_period": created.trial_period,
            "tenant_status": created.tenant_status,
            "subscription_status": created.subscription_status,
        },
    )
    saved = _load(db, lead.id)
    return _out(saved, created.code)
