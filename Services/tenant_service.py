from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.hospital_settings import HospitalSettings
from Models.opd_settings import OpdSettings
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Schemas.tenant_schema import (
    TenantRegisterRequest,
    TenantRegisterResponse,
    TenantSummary,
    TenantUpdate,
)
from Services import audit_service
from Services.invoice_service import create_first_invoice
from Services.plan_service import price_for
from hash import hash_password

IST = ZoneInfo("Asia/Kolkata")
TRIAL_DAYS = {"14 days": 14, "30 days": 30, "60 days": 60}


def _split_full_name(full_name: str) -> tuple[str, str | None]:
    parts = full_name.strip().split(None, 1)
    if not parts or not parts[0]:
        raise HTTPException(status_code=400, detail="Administrator full name is required")
    last_name = parts[1].strip() if len(parts) > 1 else None
    return parts[0], last_name or None


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def _subscription(data: TenantRegisterRequest) -> dict:
    suspended = data.tenant_status == "Suspended"
    on_trial = data.tenant_status == "Trial" or data.trial_period != "None"
    if suspended:
        subscription_status = "Suspended"
    elif on_trial:
        subscription_status = "Trial"
    else:
        subscription_status = "Active"
    started = datetime.now(IST).date()
    if on_trial and not suspended:
        renews = started + timedelta(days=TRIAL_DAYS.get(data.trial_period, 14))
    else:
        renews = _add_months(started, 12 if data.billing_cycle == "Annual" else 1)
    return {
        "plan": data.plan,
        "billing_cycle": data.billing_cycle,
        "trial_period": data.trial_period,
        "tenant_status": data.tenant_status,
        "subscription_status": subscription_status,
        "is_active": not suspended,
        "subscription_started_on": started,
        "subscription_renews_on": renews,
    }


def register_tenant(db: Session, data: TenantRegisterRequest, actor: User, *, commit: bool = True) -> TenantRegisterResponse:
    code = data.code.strip().upper()
    hospital_email = str(data.email).strip().lower()
    admin_email = str(data.admin_email).strip().lower()

    if db.query(Tenant).filter(func.upper(Tenant.code) == code).first():
        raise HTTPException(status_code=409, detail="Tenant code already registered")
    if db.query(Tenant).filter(func.lower(Tenant.email) == hospital_email).first():
        raise HTTPException(status_code=409, detail="Hospital email already registered")
    if (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(User.email) == admin_email)
        .first()
    ):
        raise HTTPException(status_code=409, detail="Administrator email already registered")

    role = db.query(Role).filter(Role.name == "admin").first()
    if not role:
        raise HTTPException(status_code=500, detail="Admin role is not seeded")

    first_name, last_name = _split_full_name(data.admin_full_name)
    subscription = _subscription(data)

    tenant = Tenant(
        name=data.name.strip(),
        code=code,
        hospital_type=data.hospital_type.strip(),
        email=hospital_email,
        phone=data.phone.strip(),
        address=data.address.strip(),
        city=data.city.strip(),
        state=data.state.strip(),
        pincode=data.pincode.strip(),
        **subscription,
    )
    db.add(tenant)
    db.flush()

    db.add(
        HospitalSettings(
            tenant_id=tenant.id,
            name=tenant.name,
            address_line1=tenant.address,
            city=tenant.city,
            state=tenant.state,
            pincode=tenant.pincode,
            phone=tenant.phone,
            email=tenant.email,
        )
    )
    db.add(
        OpdSettings(
            tenant_id=tenant.id,
            allow_patient_delete=True,
            allow_appointment_delete=True,
            allow_unpaid_bill_delete=True,
            require_admin_approval_for_delete=True,
            extra={},
        )
    )

    admin = User(
        first_name=first_name,
        last_name=last_name,
        email=admin_email,
        password=hash_password(data.admin_password),
        role_id=role.id,
        phone=data.admin_phone.strip(),
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    from Services.admin_profile_service import create_empty_admin_profile

    create_empty_admin_profile(db, admin.id)
    from seed import ensure_catalog_for_tenant

    ensure_catalog_for_tenant(db, tenant.id)
    tenant.subscription_amount = price_for(db, tenant.plan, tenant.billing_cycle)
    create_first_invoice(db, tenant)
    db.flush()
    if commit:
        db.commit()
        db.refresh(tenant)
        db.refresh(admin)
        audit_service.log_event(
            db,
            actor=actor,
            action="hospital.register",
            resource_type="tenant",
            resource_id=tenant.id,
            summary=f"Registered hospital {tenant.name} ({tenant.code})",
            details={
                "code": tenant.code,
                "admin_email": admin.email,
                "admin_user_id": admin.id,
                "plan": tenant.plan,
                "billing_cycle": tenant.billing_cycle,
                "trial_period": tenant.trial_period,
                "tenant_status": tenant.tenant_status,
                "subscription_status": tenant.subscription_status,
            },
        )

    return TenantRegisterResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        hospital_type=tenant.hospital_type,
        admin_user_id=admin.id,
        admin_email=admin.email,
        plan=tenant.plan,
        billing_cycle=tenant.billing_cycle,
        trial_period=tenant.trial_period,
        tenant_status=tenant.tenant_status,
        subscription_status=tenant.subscription_status,
        is_active=tenant.is_active,
        subscription_started_on=tenant.subscription_started_on,
        subscription_renews_on=tenant.subscription_renews_on,
    )


def _assert_platform_staff(actor: User) -> None:
    if actor.tenant_id is not None:
        raise HTTPException(
            status_code=403,
            detail="The hospital directory is only available to platform staff",
        )


def _summary(tenant: Tenant, admin: User | None) -> TenantSummary:
    return TenantSummary(
        tenant_id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        hospital_type=tenant.hospital_type,
        email=tenant.email,
        phone=tenant.phone,
        address=tenant.address,
        city=tenant.city,
        state=tenant.state,
        pincode=tenant.pincode,
        admin_user_id=admin.id if admin else None,
        admin_email=admin.email if admin else None,
        plan=tenant.plan,
        billing_cycle=tenant.billing_cycle,
        trial_period=tenant.trial_period,
        tenant_status=tenant.tenant_status,
        subscription_status=tenant.subscription_status,
        is_active=tenant.is_active,
        subscription_started_on=tenant.subscription_started_on,
        subscription_renews_on=tenant.subscription_renews_on,
        subscription_amount=tenant.subscription_amount,
        created_at=tenant.created_at,
    )


def _admins_by_tenant(db: Session, tenant_ids: list[int]) -> dict[int, User]:
    if not tenant_ids:
        return {}
    role = db.query(Role).filter(Role.name == "admin").first()
    if role is None:
        return {}
    rows = (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(User.role_id == role.id, User.tenant_id.in_(tenant_ids))
        .order_by(User.id.asc())
        .all()
    )
    admins: dict[int, User] = {}
    for user in rows:
        admins.setdefault(user.tenant_id, user)
    return admins


def list_tenants(db: Session, actor: User) -> list[TenantSummary]:
    _assert_platform_staff(actor)
    tenants = (
        db.query(Tenant)
        .order_by(Tenant.created_at.desc(), Tenant.id.desc())
        .all()
    )
    admins = _admins_by_tenant(db, [tenant.id for tenant in tenants])
    return [_summary(tenant, admins.get(tenant.id)) for tenant in tenants]


def get_tenant(db: Session, actor: User, tenant_id: int) -> TenantSummary:
    _assert_platform_staff(actor)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    admin = _admins_by_tenant(db, [tenant.id]).get(tenant.id)
    return _summary(tenant, admin)


def set_tenant_active(db: Session, actor: User, tenant_id: int, is_active: bool) -> TenantSummary:
    _assert_platform_staff(actor)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    tenant.is_active = is_active
    if is_active and tenant.tenant_status == "Suspended":
        tenant.tenant_status = "Active"
    if not is_active:
        tenant.tenant_status = "Suspended"
    db.commit()
    db.refresh(tenant)
    admin = _admins_by_tenant(db, [tenant.id]).get(tenant.id)
    return _summary(tenant, admin)


def update_tenant(db: Session, actor: User, tenant_id: int, data: TenantUpdate) -> TenantSummary:
    _assert_platform_staff(actor)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for field in ("name", "address", "phone", "plan", "billing_cycle", "subscription_renews_on"):
        if field in updates:
            setattr(tenant, field, updates[field])
    plan_changed = "plan" in updates or "billing_cycle" in updates
    if "subscription_amount" in updates:
        tenant.subscription_amount = updates["subscription_amount"]
    elif plan_changed:
        tenant.subscription_amount = price_for(db, tenant.plan, tenant.billing_cycle)
    db.commit()
    db.refresh(tenant)
    admin = _admins_by_tenant(db, [tenant.id]).get(tenant.id)
    return _summary(tenant, admin)
