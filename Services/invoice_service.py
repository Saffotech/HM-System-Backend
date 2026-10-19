from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.subscription_invoice import SubscriptionInvoice
from Models.tenant import Tenant
from Models.user import User
from Schemas.invoice_schema import PAYMENT_METHODS, InvoiceOut, RecordPayment
from Services import audit_service

IST = ZoneInfo("Asia/Kolkata")
DUE_DAYS = 14
PLAN_MONTHLY = {"Starter": 4999, "Professional": 8999, "Enterprise": 14999}


def _today():
    return datetime.now(IST).date()


def _assert_accountant(actor: User) -> None:
    if actor.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Subscription invoices are only available to platform staff")


def _person_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return name or None


def invoice_amount(plan: str, billing_cycle: str) -> int:
    monthly = PLAN_MONTHLY.get(plan, 0)
    if billing_cycle == "Annual":
        return monthly * 10
    return monthly


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
        amount=invoice_amount(tenant.plan, tenant.billing_cycle),
        invoice_date=started,
        due_date=started + timedelta(days=DUE_DAYS),
        status="Pending",
    )
    db.add(invoice)
    db.flush()
    invoice.number = f"INV-{started.year}-{invoice.id:04d}"
    return invoice


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
