"""Subscription plan prices. Existing invoice amounts are never rewritten from here."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.lead import Lead
from Models.subscription_invoice import SubscriptionInvoice
from Models.subscription_plan import SubscriptionPlan
from Models.tenant import Tenant
from Models.user import User
from Schemas.lead_schema import BILLING_CYCLES, PLAN_NAMES
from Schemas.plan_schema import PlanCreate, PlanUpdate
from Services.role_policy import caller_role_name

PLAN_MONTHLY = {"Starter": 4999, "Professional": 8999, "Enterprise": 14999}
ANNUAL_MONTHS = 10


def ensure_default_plans(db: Session) -> None:
    for name in PLAN_NAMES:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == name).first()
        if existing:
            continue
        db.add(
            SubscriptionPlan(
                name=name,
                monthly_price=PLAN_MONTHLY[name],
                annual_months_charged=ANNUAL_MONTHS,
                is_active=True,
            )
        )
    db.commit()


def _require_platform_admin(actor: User) -> None:
    if caller_role_name(actor) != "platform_admin" or actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can view subscription plans")


def _plan_row(row: SubscriptionPlan) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "monthly_price": row.monthly_price,
        "annual_price": row.monthly_price * row.annual_months_charged,
        "annual_months_charged": row.annual_months_charged,
        "billing_cycles": list(BILLING_CYCLES),
        "is_active": bool(row.is_active),
    }


def price_for(db: Session, plan: str, billing_cycle: str) -> int:
    if billing_cycle not in BILLING_CYCLES:
        raise HTTPException(status_code=422, detail="Choose a subscription plan and billing cycle.")
    row = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.name == plan, SubscriptionPlan.is_active.is_(True))
        .first()
    )
    if row is None and plan in PLAN_MONTHLY:
        monthly = PLAN_MONTHLY[plan]
        factor = ANNUAL_MONTHS
    elif row is None:
        raise HTTPException(status_code=422, detail="Choose a subscription plan and billing cycle.")
    else:
        monthly = row.monthly_price
        factor = row.annual_months_charged
    if billing_cycle == "Annual":
        return int(monthly) * int(factor)
    return int(monthly)


def list_plans(db: Session, actor: User) -> list[dict]:
    _require_platform_admin(actor)
    rows = (
        db.query(SubscriptionPlan)
        .order_by(SubscriptionPlan.is_active.desc(), SubscriptionPlan.monthly_price.asc(), SubscriptionPlan.id.asc())
        .all()
    )
    if not rows:
        return [
            {
                "name": name,
                "monthly_price": PLAN_MONTHLY[name],
                "annual_price": PLAN_MONTHLY[name] * ANNUAL_MONTHS,
                "billing_cycles": list(BILLING_CYCLES),
                "is_active": True,
            }
            for name in PLAN_NAMES
        ]
    return [_plan_row(row) for row in rows]


def _name_taken(db: Session, name: str, except_id: int | None = None) -> bool:
    query = db.query(SubscriptionPlan.id).filter(SubscriptionPlan.name == name)
    if except_id is not None:
        query = query.filter(SubscriptionPlan.id != except_id)
    return query.first() is not None


def create_plan(db: Session, actor: User, data: PlanCreate) -> dict:
    _require_platform_admin(actor)
    if _name_taken(db, data.name):
        raise HTTPException(status_code=409, detail="A plan with this name already exists.")
    row = SubscriptionPlan(
        name=data.name,
        monthly_price=data.monthly_price,
        annual_months_charged=data.annual_months_charged,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_row(row)


def update_plan(db: Session, actor: User, plan_id: int, data: PlanUpdate) -> dict:
    _require_platform_admin(actor)
    row = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != row.name and _name_taken(db, updates["name"], row.id):
        raise HTTPException(status_code=409, detail="A plan with this name already exists.")
    for field, value in updates.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _plan_row(row)


def deactivate_plan(db: Session, actor: User, plan_id: int) -> dict:
    """Hide the plan from new sales. Hospitals and invoices already using it stay as they are."""
    _require_platform_admin(actor)
    row = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="This plan is already inactive.")
    row.is_active = False
    db.commit()
    db.refresh(row)
    return _plan_row(row)


def activate_plan(db: Session, actor: User, plan_id: int) -> dict:
    """Offer the plan for new sales again. Existing hospital amounts are not rewritten."""
    _require_platform_admin(actor)
    row = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if row.is_active:
        raise HTTPException(status_code=409, detail="This plan is already active.")
    row.is_active = True
    db.commit()
    db.refresh(row)
    return _plan_row(row)


def delete_plan(db: Session, actor: User, plan_id: int) -> None:
    """Remove a catalog plan that no hospital, lead, or invoice still names."""
    _require_platform_admin(actor)
    row = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    used = (
        db.query(Tenant.id).filter(Tenant.plan == row.name).first()
        or db.query(Lead.id).filter(Lead.plan == row.name).first()
        or db.query(SubscriptionInvoice.id).filter(SubscriptionInvoice.plan == row.name).first()
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail="This plan is still used by a hospital, lead, or invoice. Deactivate it instead.",
        )
    db.delete(row)
    db.commit()
