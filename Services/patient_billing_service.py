"""Billing & Payments on the patient Profile tab.

A patient sees only their own bills. Two kinds exist:

- OPD bill  = OpdVisit. The patient can pay it from the app.
- IPD bill  = IpdBill (final only). Read-only here; IPD payment is taken at the desk.

Invoices and payment recording reuse the same functions the desk uses.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.department import Department
from Models.ipd import IpdAdmission, IpdBill, IpdInsuranceClaim, IpdPaymentTransaction
from Models.opd_billing import PaymentTransaction
from Models.patient import OpdVisit
from Models.user import User
from Schemas.opd_schema import CollectPayment
from Schemas.patient_profile_schema import PatientPayVisit
from Services import ipd_service, opd_helpers as opd_h, opd_service, opd_settings_service
from Services.patient_portal_service import patient_for_user

# Anything with less than this left to pay counts as settled.
_BALANCE_EPSILON = 0.01
_EARLIEST = datetime.min.replace(tzinfo=opd_h.IST)


def _opd_bill_item(visit: OpdVisit, department: Department | None) -> dict:
    balance = float(visit.balance_due or 0)
    return {
        "kind": "opd",
        "id": visit.id,
        "bill_number": visit.bill_number,
        "description": f"OPD · {department.name}" if department else "OPD consultation",
        "bill_date": visit.visit_date,
        "grand_total": float(visit.grand_total or 0),
        "paid_amount": float(visit.paid_amount or 0),
        "balance_due": balance,
        "payment_status": visit.payment_status,
        "appointment_id": visit.appointment_id,
        "can_pay": balance > _BALANCE_EPSILON,
    }


def _ipd_bill_item(bill: IpdBill, admission: IpdAdmission) -> dict:
    return {
        "kind": "ipd",
        "id": bill.id,
        "bill_number": bill.bill_number,
        "description": f"IPD stay · {admission.admission_no}",
        "bill_date": bill.generated_at,
        "grand_total": float(bill.grand_total or 0),
        "paid_amount": float(bill.paid_amount or 0),
        "balance_due": float(bill.balance_due or 0),
        "payment_status": bill.payment_status,
        "appointment_id": None,
        # IPD payment is taken at the hospital desk.
        "can_pay": False,
    }


def _all_bill_items(db: Session, patient_id: int) -> list[dict]:
    opd_rows = (
        db.query(OpdVisit, Department)
        .outerjoin(Department, OpdVisit.department_id == Department.id)
        .filter(OpdVisit.patient_id == patient_id, OpdVisit.status != "cancelled")
        .all()
    )
    ipd_rows = (
        db.query(IpdBill, IpdAdmission)
        .join(IpdAdmission, IpdBill.admission_id == IpdAdmission.id)
        .filter(IpdAdmission.patient_id == patient_id, IpdBill.status == "final")
        .all()
    )
    items = [_opd_bill_item(visit, department) for visit, department in opd_rows]
    items += [_ipd_bill_item(bill, admission) for bill, admission in ipd_rows]
    items.sort(key=lambda item: item["bill_date"] or _EARLIEST, reverse=True)
    return items


def list_bills(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    items = _all_bill_items(db, patient.id)
    return {"total": len(items), "bills": items}


def outstanding_balance(db: Session, patient_id: int) -> tuple[float, list[dict]]:
    pending = [
        item
        for item in _all_bill_items(db, patient_id)
        if item["balance_due"] > _BALANCE_EPSILON
    ]
    total = round(sum(item["balance_due"] for item in pending), 2)
    return total, pending


def summary(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    total, pending = outstanding_balance(db, patient.id)
    return {
        "outstanding_balance": total,
        "pending_bills": pending,
    }


def receipts(db: Session, patient_id: int) -> list[dict]:
    opd_rows = (
        db.query(PaymentTransaction, OpdVisit)
        .join(OpdVisit, PaymentTransaction.visit_id == OpdVisit.id)
        .filter(OpdVisit.patient_id == patient_id)
        .all()
    )
    ipd_rows = (
        db.query(IpdPaymentTransaction, IpdBill)
        .join(IpdBill, IpdPaymentTransaction.bill_id == IpdBill.id)
        .join(IpdAdmission, IpdBill.admission_id == IpdAdmission.id)
        .filter(IpdAdmission.patient_id == patient_id)
        .all()
    )
    items = [
        {
            "kind": "opd",
            "receipt_id": txn.id,
            "bill_id": visit.id,
            "bill_number": visit.bill_number,
            "amount": float(txn.amount),
            "payment_mode": txn.payment_mode,
            "transaction_reference": txn.transaction_reference,
            "paid_at": txn.paid_at,
        }
        for txn, visit in opd_rows
    ]
    items += [
        {
            "kind": "ipd",
            "receipt_id": txn.id,
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "amount": float(txn.amount),
            "payment_mode": txn.payment_mode,
            "transaction_reference": txn.transaction_reference,
            "paid_at": txn.paid_at,
        }
        for txn, bill in ipd_rows
    ]
    items.sort(key=lambda item: item["paid_at"] or _EARLIEST, reverse=True)
    return items


def list_payments(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    items = receipts(db, patient.id)
    return {"total": len(items), "payments": items}


def list_insurance_claims(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    rows = (
        db.query(IpdInsuranceClaim, IpdAdmission)
        .join(IpdAdmission, IpdInsuranceClaim.admission_id == IpdAdmission.id)
        .filter(IpdInsuranceClaim.patient_id == patient.id)
        .order_by(IpdInsuranceClaim.created_at.desc())
        .all()
    )
    claims = [
        {
            "claim_id": claim.id,
            "admission_id": admission.id,
            "admission_no": admission.admission_no,
            "claim_type": claim.claim_type,
            "insurer": claim.insurer,
            "policy_no": claim.policy_no,
            "claimed_amount": float(claim.claimed_amount or 0),
            "approved_amount": float(claim.approved_amount or 0),
            "claim_status": claim.claim_status,
            "policy_status": claim.policy_status,
            "created_at": claim.created_at,
        }
        for claim, admission in rows
    ]
    return {"total": len(claims), "claims": claims}


def _own_visit(db: Session, patient_id: int, visit_id: int) -> OpdVisit:
    visit = (
        db.query(OpdVisit)
        .filter(
            OpdVisit.id == visit_id,
            OpdVisit.patient_id == patient_id,
            OpdVisit.status != "cancelled",
        )
        .first()
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return visit


def opd_invoice(db: Session, user: User, visit_id: int) -> dict:
    patient = patient_for_user(db, user)
    visit = _own_visit(db, patient.id, visit_id)
    return opd_service.build_invoice(db, visit.id)


def ipd_invoice(db: Session, user: User, bill_id: int) -> dict:
    patient = patient_for_user(db, user)
    bill = (
        db.query(IpdBill)
        .join(IpdAdmission, IpdBill.admission_id == IpdAdmission.id)
        .filter(
            IpdBill.id == bill_id,
            IpdBill.status == "final",
            IpdAdmission.patient_id == patient.id,
        )
        .first()
    )
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return ipd_service.build_invoice(db, bill.id)


def pay_visit(db: Session, user: User, visit_id: int, data: PatientPayVisit) -> dict:
    """Pay any of this patient's OPD bills, with or without an appointment."""
    patient = patient_for_user(db, user)
    visit = _own_visit(db, patient.id, visit_id)
    opd_settings_service.validate_payment_mode(db, payment_mode=data.payment_mode)
    return opd_service.collect_payment(
        db,
        visit.id,
        CollectPayment(
            payment_mode=data.payment_mode,
            paid_amount=data.paid_amount,
            transaction_reference=data.transaction_reference,
        ),
        user.id,
    )
