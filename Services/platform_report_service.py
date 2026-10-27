"""Read-only platform totals. Invoice rows and lead rows are not changed."""
from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from Models.lead import Lead
from Models.role import Role
from Models.subscription_invoice import SubscriptionInvoice
from Models.user import User
from Services.invoice_service import _today
from Services.lead_service import _lead_query, _person_name, _summary
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
    failed_amount = func.coalesce(
        func.sum(case((SubscriptionInvoice.status == "Failed", SubscriptionInvoice.amount), else_=0)),
        0,
    )
    row = db.query(
        collected, pending, overdue, paid_count, pending_count, overdue_count, failed_count, failed_amount
    ).one()
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
        "failed_amount": int(row[7] or 0),
        "failed_count": int(row[6] or 0),
        "outstanding_amount": pending_amount + overdue_amount,
        "invoice_count": int(row[3] or 0) + int(row[4] or 0) + int(row[5] or 0) + int(row[6] or 0),
        "invoices": _revenue_invoices(db, today),
    }


def _revenue_bucket(invoice: SubscriptionInvoice, today) -> str | None:
    if invoice.status == "Paid":
        return "collected"
    if invoice.status == "Failed":
        return "failed"
    if invoice.status == "Pending":
        return "overdue" if invoice.due_date < today else "pending"
    return None


def _revenue_invoices(db: Session, today) -> list[dict]:
    rows = (
        db.query(SubscriptionInvoice)
        .options(joinedload(SubscriptionInvoice.hospital))
        .order_by(SubscriptionInvoice.invoice_date.desc(), SubscriptionInvoice.id.desc())
        .all()
    )
    invoices = []
    for invoice in rows:
        bucket = _revenue_bucket(invoice, today)
        if bucket is None:
            continue
        hospital = invoice.hospital
        paid_on = None
        amount = invoice.amount
        if bucket == "collected":
            paid_on = (invoice.paid_at or invoice.invoice_date).isoformat()
            amount = invoice.payment_amount if invoice.payment_amount is not None else invoice.amount
        invoices.append(
            {
                "id": invoice.id,
                "number": invoice.number,
                "tenant_id": invoice.tenant_id,
                "hospital_name": hospital.name if hospital else "",
                "hospital_code": hospital.code if hospital else "",
                "plan": invoice.plan,
                "billing_cycle": invoice.billing_cycle,
                "amount": int(amount),
                "payment_amount": invoice.payment_amount,
                "invoice_date": invoice.invoice_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "paid_at": paid_on,
                "paid_date": paid_on,
                "status": "Overdue" if bucket == "overdue" else invoice.status,
                "bucket": bucket,
            }
        )
    return invoices


def crm_analytics(db: Session, actor: User) -> dict:
    _require_platform_admin(actor)
    rows = db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    counts = {status: 0 for status in LEAD_STATUSES}
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    counts["total"] = sum(counts.values())
    return {"statuses": counts}


def crm_performance(db: Session, actor: User) -> dict:
    """Every CRM lead and the paid invoices of hospitals those leads became.

    The CRM lead list stays limited to the signed-in CRM user. This report is
    only for the platform admin screen that compares employees.
    """
    _require_platform_admin(actor)
    employees = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(User.tenant_id.is_(None), Role.name == "crm")
        .order_by(User.first_name.asc(), User.id.asc())
        .all()
    )
    leads = _lead_query(db).order_by(Lead.created_at.desc(), Lead.id.desc()).all()
    hospital_ids = {lead.hospital_id for lead in leads if lead.hospital_id}
    invoices = []
    if hospital_ids:
        invoices = (
            db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.tenant_id.in_(hospital_ids),
                SubscriptionInvoice.status == "Paid",
            )
            .all()
        )
    return {
        "employees": [
            {"id": user.id, "name": _person_name(user) or user.email}
            for user in employees
        ],
        "leads": [
            {**_summary(lead, actor).model_dump(), "assignee_name": _person_name(lead.assignee) or None}
            for lead in leads
        ],
        "paid_invoices": [
            {
                "tenant_id": invoice.tenant_id,
                "amount": invoice.amount,
                "payment_amount": invoice.payment_amount,
                "invoice_date": invoice.invoice_date.isoformat(),
                "status": "Paid",
            }
            for invoice in invoices
        ],
    }
