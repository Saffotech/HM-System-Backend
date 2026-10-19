from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.invoice_schema import InvoiceOut, RecordPayment
from Services.invoice_service import list_invoices, record_payment
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/invoices", tags=["Platform Invoices"])


@router.get("", response_model=list[InvoiceOut])
def read_invoices(
    status: str = Query("All"),
    tenant_id: int | None = None,
    due: str = Query("All"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("invoices:manage")),
):
    return list_invoices(db, current_user, status, tenant_id, due)


@router.post("/{invoice_id}/payments", response_model=InvoiceOut)
def pay_invoice(
    invoice_id: int,
    data: RecordPayment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("invoices:manage")),
):
    return record_payment(db, current_user, invoice_id, data)
