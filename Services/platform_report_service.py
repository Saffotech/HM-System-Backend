"""Read-only platform totals. Invoice rows and lead rows are not changed."""
from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from Models.lead import Lead
from Models.subscription_invoice import SubscriptionInvoice
from Models.user import User
from Services.invoice_service import _today
from Services.role_policy import caller_role_name

LEAD_STATUSES = ("New", "Contacted", "Agreed", "Registered", "Not Interested")


def _require_platform_admin(actor: User) -> None:
    if caller_role_name(actor) != "platform_admin" or actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can view this report")


def revenue_report(db: Session, actor: User) -> dict:
    _require_platform_admin(actor)
    today = _today()
    paid_amount = func.coalesce(SubscriptionInvoice.payment_amount, SubscriptionInvoice.amount)
    collected = func.coalesce(func.sum(case((SubscriptionInvoice.status == "Paid", paid_amount), else_=0)), 0)
    pending = func.coalesce(
        func.sum(
            case(
                (
                    (SubscriptionInvoice.status == "Pending") & (SubscriptionInvoice.due_date >= today),
                    SubscriptionInvoice.amount,
                ),
                else_=0,
            )
        ),
        0,
    )
    overdue = func.coalesce(
        func.sum(
            case(
                (
                    (SubscriptionInvoice.status == "Pending") & (SubscriptionInvoice.due_date < today),
                    SubscriptionInvoice.amount,
                ),
                else_=0,
            )
        ),
        0,
    )
    paid_count = func.coalesce(func.sum(case((SubscriptionInvoice.status == "Paid", 1), else_=0)), 0)
    pending_count = func.coalesce(
        func.sum(
            case(
                (
                    (SubscriptionInvoice.status == "Pending") & (SubscriptionInvoice.due_date >= today),
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    overdue_count = func.coalesce(
        func.sum(
            case(
                (
                    (SubscriptionInvoice.status == "Pending") & (SubscriptionInvoice.due_date < today),
                    1,
                ),
                else_=0,
            )
        ),
        0,
    )
    failed_count = func.coalesce(func.sum(case((SubscriptionInvoice.status == "Failed", 1), else_=0)), 0)
    row = db.query(collected, pending, overdue, paid_count, pending_count, overdue_count, failed_count).one()
    collected_amount = int(row[0] or 0)
    pending_amount = int(row[1] or 0)
    overdue_amount = int(row[2] or 0)
    return {
        "collected_amount": collected_amount,
        "collected_count": int(row[3] or 0),
        "pending_amount": pending_amount,
        "pending_count": int(row[4] or 0),
        "overdue_amount": overdue_amount,
        "overdue_count": int(row[5] or 0),
        "failed_count": int(row[6] or 0),
        "outstanding_amount": pending_amount + overdue_amount,
        "invoice_count": int(row[3] or 0) + int(row[4] or 0) + int(row[5] or 0) + int(row[6] or 0),
    }


def crm_analytics(db: Session, actor: User) -> dict:
    _require_platform_admin(actor)
    rows = db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    counts = {status: 0 for status in LEAD_STATUSES}
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    counts["total"] = sum(counts.values())
    return {"statuses": counts}
