"""Patient Billing & Payments.

OPD bills can be paid from the app. IPD bills are read-only here.
Invoices return the same data the desk prints, as JSON.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from Models.user import User
from Schemas.patient_profile_schema import PatientPayVisit
from Services import patient_billing_service

router = APIRouter(prefix="/patient/billing", tags=["Patient Billing"])


@router.get("/summary")
def billing_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Outstanding balance and the bills that still have money due."""
    return patient_billing_service.summary(db, current_user)


@router.get("/bills")
def list_bills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every OPD and IPD bill, newest first."""
    return patient_billing_service.list_bills(db, current_user)


@router.get("/payments")
def list_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Payment history and receipts."""
    return patient_billing_service.list_payments(db, current_user)


@router.get("/insurance-claims")
def list_insurance_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_billing_service.list_insurance_claims(db, current_user)


@router.get("/opd/{visit_id}/invoice")
def opd_invoice(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_billing_service.opd_invoice(db, current_user, visit_id)


@router.get("/ipd/{bill_id}/invoice")
def ipd_invoice(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_billing_service.ipd_invoice(db, current_user, bill_id)


@router.post("/opd/{visit_id}/pay")
def pay_opd_bill(
    visit_id: int,
    data: PatientPayVisit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_billing_service.pay_visit(db, current_user, visit_id, data)
