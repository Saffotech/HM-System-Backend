"""Paid subscription revenue for hospitals registered from the signed-in CRM user's leads."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from Models.lead import Lead
from Models.subscription_invoice import SubscriptionInvoice
from Models.tenant import Tenant
from Models.user import User
from Services.invoice_service import _today
from Services.role_policy import caller_role_name


def _require_crm(actor: User) -> None:
    if caller_role_name(actor) != "crm" or actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only a CRM user can view attributed revenue")


def _month_start(day: date, offset: int) -> date:
    index = day.year * 12 + (day.month - 1) + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def crm_revenue(db: Session, actor: User) -> dict:
    _require_crm(actor)
    hospital_ids = [
        row[0]
        for row in db.query(Lead.hospital_id)
        .filter(
            Lead.assigned_to == actor.id,
            Lead.status == "Registered",
            Lead.hospital_id.isnot(None),
        )
        .distinct()
        .all()
    ]
    if not hospital_ids:
        today = _today()
        months = []
        for offset in range(-5, 1):
            start = _month_start(today, offset)
            months.append({"year": start.year, "month": start.month, "amount": 0})
        return {
            "collected_amount": 0,
            "collected_count": 0,
            "hospitals": [],
            "months": months,
        }

    paid_amount = func.coalesce(SubscriptionInvoice.payment_amount, SubscriptionInvoice.amount)
    hospital_rows = (
        db.query(
            Tenant.id,
            Tenant.name,
            Tenant.plan,
            func.coalesce(func.sum(paid_amount), 0),
            func.count(SubscriptionInvoice.id),
        )
        .outerjoin(
            SubscriptionInvoice,
            (SubscriptionInvoice.tenant_id == Tenant.id) & (SubscriptionInvoice.status == "Paid"),
        )
        .filter(Tenant.id.in_(hospital_ids))
        .group_by(Tenant.id, Tenant.name, Tenant.plan)
        .order_by(Tenant.name.asc())
        .all()
    )
    hospitals = [
        {
            "tenant_id": row[0],
            "hospital_name": row[1],
            "plan": row[2],
            "paid_amount": int(row[3] or 0),
            "paid_count": int(row[4] or 0),
        }
        for row in hospital_rows
    ]
    collected_amount = sum(item["paid_amount"] for item in hospitals)
    collected_count = sum(item["paid_count"] for item in hospitals)

    today = _today()
    start = _month_start(today, -5)
    month_rows = (
        db.query(
            extract("year", SubscriptionInvoice.invoice_date),
            extract("month", SubscriptionInvoice.invoice_date),
            func.coalesce(func.sum(paid_amount), 0),
        )
        .filter(
            SubscriptionInvoice.tenant_id.in_(hospital_ids),
            SubscriptionInvoice.status == "Paid",
            SubscriptionInvoice.invoice_date >= start,
        )
        .group_by(
            extract("year", SubscriptionInvoice.invoice_date),
            extract("month", SubscriptionInvoice.invoice_date),
        )
        .all()
    )
    by_month = {(int(year), int(month)): int(amount or 0) for year, month, amount in month_rows}
    months = []
    for offset in range(-5, 1):
        point = _month_start(today, offset)
        months.append(
            {
                "year": point.year,
                "month": point.month,
                "amount": by_month.get((point.year, point.month), 0),
            }
        )
    return {
        "collected_amount": collected_amount,
        "collected_count": collected_count,
        "hospitals": hospitals,
        "months": months,
    }
