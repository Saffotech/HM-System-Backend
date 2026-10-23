"""Subscription plan prices. Existing invoice amounts are never rewritten from here."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.subscription_plan import SubscriptionPlan
from Models.user import User
from Schemas.lead_schema import BILLING_CYCLES, PLAN_NAMES
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


def price_for(db: Session, plan: str, billing_cycle: str) -> int:
    if plan not in PLAN_NAMES or billing_cycle not in BILLING_CYCLES:
        raise HTTPException(status_code=422, detail="Choose a subscription plan and billing cycle.")
    row = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.name == plan, SubscriptionPlan.is_active.is_(True))
        .first()
    )
    monthly = row.monthly_price if row else PLAN_MONTHLY[plan]
    factor = row.annual_months_charged if row else ANNUAL_MONTHS
    if billing_cycle == "Annual":
        return int(monthly) * int(factor)
    return int(monthly)


def list_plans(db: Session, actor: User) -> list[dict]:
    if caller_role_name(actor) != "platform_admin" or actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can view subscription plans")
    rows = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.monthly_price.asc())
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
    return [
        {
            "name": row.name,
            "monthly_price": row.monthly_price,
            "annual_price": row.monthly_price * row.annual_months_charged,
            "billing_cycles": list(BILLING_CYCLES),
            "is_active": bool(row.is_active),
        }
        for row in rows
    ]
