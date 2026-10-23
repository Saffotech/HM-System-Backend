from datetime import datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.subscription_invoice import SubscriptionInvoice
from Models.tenant import Tenant
from Models.user import User
from Schemas.invoice_schema import PAYMENT_METHODS, InvoiceOut, RecordPayment
from Services import audit_service
from Services.plan_service import price_for

IST = ZoneInfo("Asia/Kolkata")
DUE_DAYS = 14


def _today():
    return datetime.now(IST).date()


def _add_months(start, months: int):
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))


def _assert_accountant(actor: User) -> None:
    if actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Subscription invoices are only available to platform staff")


def _person_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return name or None


def invoice_amount(db: Session, tenant: Tenant) -> int:
    """Amount for the next invoice. A stored contract wins over the live catalog."""
    stored = getattr(tenant, "subscription_amount", None)
    if stored:
        return int(stored)
    return price_for(db, tenant.plan, tenant.billing_cycle)


def display_status(invoice: SubscriptionInvoice, today=None) -> str:
    today = today or _today()
    if invoice.status == "Pending" and invoice.due_date < today:
        return "Overdue"
    return invoice.status


def create_first_invoice(db: Session, tenant: Tenant) -> SubscriptionInvoice | None:
    """Bill the first period when the hospital is not on a trial or suspended."""
    if tenant.subscription_status != "Active":
        return None
    if db.query(SubscriptionInvoice.id).filter(SubscriptionInvoice.tenant_id == tenant.id).first():
        return None
    started = tenant.subscription_started_on
    invoice = SubscriptionInvoice(
        number=f"pending-{tenant.id}",
        tenant_id=tenant.id,
        plan=tenant.plan,
        billing_cycle=tenant.billing_cycle,
        amount=invoice_amount(db, tenant),
        invoice_date=started,
        due_date=started + timedelta(days=DUE_DAYS),
        status="Pending",
    )
    db.add(invoice)
    db.flush()
    invoice.number = f"INV-{started.year}-{invoice.id:04d}"
    return invoice


def _period_exists(db: Session, tenant_id: int, period) -> bool:
    return (
        db.query(SubscriptionInvoice.id)
        .filter(
            SubscriptionInvoice.tenant_id == tenant_id,
            SubscriptionInvoice.invoice_date == period,
        )
        .first()
        is not None
    )


def _add_period_invoice(db: Session, tenant: Tenant, period) -> bool:
    if _period_exists(db, tenant.id, period):
        return False
    invoice = SubscriptionInvoice(
        number=f"pending-{tenant.id}-{period.isoformat()}",
        tenant_id=tenant.id,
        plan=tenant.plan,
        billing_cycle=tenant.billing_cycle,
        amount=invoice_amount(db, tenant),
        invoice_date=period,
        due_date=period + timedelta(days=DUE_DAYS),
        status="Pending",
    )
    db.add(invoice)
    db.flush()
    invoice.number = f"INV-{period.year}-{invoice.id:04d}"
    return True


def generate_renewal_invoices(db: Session) -> int:
    """Create the next invoice for each active hospital whose period has ended.

    Safe to run repeatedly: a period that already has an invoice is skipped,
    and the renewal date moves forward only after that period is recorded.
    """
    today = _today()
    due_ids = [
        row.id
        for row in db.query(Tenant.id)
        .filter(
            Tenant.subscription_status == "Active",
            Tenant.is_active.is_(True),
            Tenant.tenant_status == "Active",
            Tenant.trial_period == "None",
            Tenant.subscription_renews_on <= today,
        )
        .all()
    ]
    created = 0
    for tenant_id in due_ids:
        locked = db.query(Tenant).filter(Tenant.id == tenant_id).with_for_update().one()
        guard = 0
        while (
            locked.subscription_status == "Active"
            and locked.is_active
            and locked.tenant_status == "Active"
            and (locked.trial_period or "None") == "None"
            and locked.subscription_renews_on is not None
            and locked.subscription_renews_on <= today
            and guard < 36
        ):
            period = locked.subscription_renews_on
            if _add_period_invoice(db, locked, period):
                created += 1
            months = 12 if locked.billing_cycle == "Annual" else 1
            locked.subscription_renews_on = _add_months(period, months)
            guard += 1
    db.commit()
    return created


def _out(invoice: SubscriptionInvoice) -> InvoiceOut:
    hospital = invoice.hospital
    return InvoiceOut(
        id=invoice.id,
        number=invoice.number,
        tenant_id=invoice.tenant_id,
        hospital_name=hospital.name if hospital else "",
        hospital_code=hospital.code if hospital else "",
        plan=invoice.plan,
        billing_cycle=invoice.billing_cycle,
        subscription_status=hospital.subscription_status if hospital else "",
        amount=invoice.amount,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        status=display_status(invoice),
        method=invoice.method,
        reference=invoice.reference,
        paid_at=invoice.paid_at,
        notes=invoice.notes,
        payment_amount=invoice.payment_amount,
        recorded_by_name=_person_name(invoice.recorder),
    )


def _query(db: Session):
    return db.query(SubscriptionInvoice).options(
        joinedload(SubscriptionInvoice.hospital),
        joinedload(SubscriptionInvoice.recorder),
    )


def list_invoices(
    db: Session,
    actor: User,
    status: str = "All",
    tenant_id: int | None = None,
    due: str = "All",
) -> list[InvoiceOut]:
    _assert_accountant(actor)
    if status not in ("All", "Pending", "Overdue", "Paid", "Failed"):
        raise HTTPException(status_code=422, detail="Status must be All, Pending, Overdue, Paid, or Failed.")
    if due not in ("All", "today", "month"):
        raise HTTPException(status_code=422, detail="Due must be All, today, or month.")
    rows = _query(db).order_by(SubscriptionInvoice.due_date.asc(), SubscriptionInvoice.id.desc())
    if tenant_id is not None:
        rows = rows.filter(SubscriptionInvoice.tenant_id == tenant_id)
    today = _today()
    invoices = []
    for invoice in rows.all():
        shown = display_status(invoice, today)
        if status != "All" and shown != status:
            continue
        if due == "today" and invoice.due_date != today:
            continue
        if due == "month" and (invoice.due_date.year, invoice.due_date.month) != (today.year, today.month):
            continue
        invoices.append(_out(invoice))
    return invoices


def record_payment(db: Session, actor: User, invoice_id: int, data: RecordPayment) -> InvoiceOut:
    _assert_accountant(actor)
    if data.paid_at > _today():
        raise HTTPException(status_code=422, detail="The payment date can't be in the future.")
    if data.method != "Card" and not data.reference:
        raise HTTPException(status_code=422, detail="Enter the payment reference.")
    if data.method not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Choose a payment method.")
    invoice = (
        db.query(SubscriptionInvoice)
        .filter(SubscriptionInvoice.id == invoice_id)
        .with_for_update()
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "Paid":
        raise HTTPException(status_code=409, detail="This invoice is already paid.")
    if data.amount != invoice.amount:
        raise HTTPException(status_code=422, detail="Enter the full invoice amount.")
    invoice.status = "Paid"
    invoice.method = data.method
    invoice.reference = data.reference
    invoice.paid_at = data.paid_at
    invoice.notes = data.notes
    invoice.payment_amount = data.amount
    invoice.recorded_by = actor.id
    audit_service.log_event(
        db,
        actor=actor,
        action="invoice.pay",
        resource_type="subscription_invoice",
        resource_id=invoice.id,
        summary=f"Recorded payment for {invoice.number}",
        details={"amount": data.amount, "method": data.method, "tenant_id": invoice.tenant_id},
    )
    saved = _query(db).filter(SubscriptionInvoice.id == invoice.id).one()
    return _out(saved)
