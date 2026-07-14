"""Shared OPD helpers used across opd services."""
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.opd_billing import BillItem, PaymentTransaction
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DOCTOR_ROLE = "doctor"
VALID_PAYMENT_MODES = frozenset({"cash", "card", "upi", "insurance"})


def now_ist() -> datetime:
    return datetime.now(IST)


def today_start_ist() -> datetime:
    return now_ist().replace(hour=0, minute=0, second=0, microsecond=0)


def today_ist_date():
    """Calendar date in Asia/Kolkata (use for queue_date and daily filters)."""
    return now_ist().date()


def display_name(first: str, last: Optional[str] = None, prefix: str = "") -> str:
    return f"{prefix}{first} {last or ''}".strip()


def validate_payment_mode(payment_mode: str) -> None:
    if payment_mode not in VALID_PAYMENT_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment_mode. Use: {', '.join(sorted(VALID_PAYMENT_MODES))}",
        )


def ensure_immediate_payment_valid(
    payment_mode: str,
    pay_later: bool,
    paid: float,
    transaction_reference: Optional[str] = None,
) -> None:
    """Validate payment mode and card/upi reference when recording payment now."""
    if pay_later or paid <= 0:
        return
    validate_payment_mode(payment_mode)
    ref = (transaction_reference or "").strip()
    if payment_mode in ("card", "upi") and not ref:
        raise HTTPException(
            status_code=400,
            detail=(
                "transaction_reference is required when payment_mode is 'card' or 'upi'. "
                "Send the UPI UTR / Card RRN or approval code from the payment receipt."
            ),
        )


def bill_totals_from_subtotal(subtotal: float, gst_percent: float) -> Tuple[float, float, float]:
    gst_amount = round(subtotal * gst_percent / 100, 2)
    return subtotal, gst_amount, round(subtotal + gst_amount, 2)


def bill_totals(registration_fee: float, consultation_fee: float, gst_percent: float) -> Tuple[float, float, float]:
    return bill_totals_from_subtotal(registration_fee + consultation_fee, gst_percent)


def get_department(db: Session, department_id: int) -> Department:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


def get_doctor_in_department(db: Session, doctor_id: int, department_id: int) -> User:
    doctor = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(
            User.id == doctor_id,
            User.department_id == department_id,
            User.is_active.is_(True),
            Role.name == DOCTOR_ROLE,
        )
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found in the selected department")
    return doctor


def list_doctors_in_department(db: Session, department_id: int) -> Tuple[Department, list[User]]:
    dept = get_department(db, department_id)
    doctors = (
        db.query(User)
        .options(joinedload(User.doctor_profile))
        .join(Role, User.role_id == Role.id)
        .filter(
            User.department_id == department_id,
            User.is_active.is_(True),
            Role.name == DOCTOR_ROLE,
        )
        .all()
    )
    return dept, doctors


def next_patient_uid(db: Session) -> str:
    last = db.query(func.max(Patient.id)).scalar()
    return f"P-{1000 + (last or 0) + 1}"


def next_visit_numbers(db: Session) -> Tuple[str, str]:
    last = db.query(func.max(OpdVisit.id)).scalar() or 0
    seq = last + 1
    today = now_ist().strftime("%Y%m%d")
    return f"BILL-{seq:03d}", f"OPD-{today}-{seq:03d}"


def next_appointment_uid(db: Session) -> str:
    from Models.opd_billing import Appointment

    last = db.query(func.max(Appointment.id)).scalar() or 0
    return f"APT-{last + 1:04d}"


def get_patient(db: Session, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.is_active.is_(True)).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def get_visit_with_relations(db: Session, visit_id: int):
    row = (
        db.query(OpdVisit, Patient, User, Department)
        .join(Patient, OpdVisit.patient_id == Patient.id)
        .outerjoin(User, OpdVisit.doctor_id == User.id)
        .outerjoin(Department, OpdVisit.department_id == Department.id)
        .filter(OpdVisit.id == visit_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Visit not found")
    return row


def save_default_bill_items(db: Session, visit: OpdVisit, doctor: Optional[User]) -> None:
    consultation_label = (
        f"Dr. {doctor.first_name} Consultation" if doctor else "Doctor Consultation"
    )
    db.add_all(
        [
            BillItem(
                visit_id=visit.id,
                description="Registration Fee",
                qty=1,
                unit_price=visit.registration_fee,
                amount=visit.registration_fee,
            ),
            BillItem(
                visit_id=visit.id,
                description=consultation_label,
                qty=1,
                unit_price=visit.consultation_fee,
                amount=visit.consultation_fee,
            ),
        ]
    )


def save_extra_bill_items(db: Session, visit_id: int, items: List[dict]) -> float:
    total = 0.0
    for item in items:
        amount = round(item["qty"] * item["unit_price"], 2)
        db.add(
            BillItem(
                visit_id=visit_id,
                description=item["description"],
                qty=item["qty"],
                unit_price=item["unit_price"],
                amount=amount,
            )
        )
        total += amount
    return total


def list_bill_items(db: Session, visit_id: int) -> List[BillItem]:
    return db.query(BillItem).filter(BillItem.visit_id == visit_id).all()


def record_payment(
    db: Session,
    visit: OpdVisit,
    amount: float,
    payment_mode: str,
    recorded_by: int,
    transaction_reference: Optional[str] = None,
) -> PaymentTransaction:
    ensure_immediate_payment_valid(payment_mode, pay_later=False, paid=amount, transaction_reference=transaction_reference)
    txn = PaymentTransaction(
        visit_id=visit.id,
        amount=amount,
        payment_mode=payment_mode,
        transaction_reference=transaction_reference,
        paid_at=now_ist(),
        recorded_by=recorded_by,
    )
    db.add(txn)
    new_paid = round((visit.paid_amount or 0) + amount, 2)
    visit.paid_amount = new_paid
    visit.payment_mode = payment_mode
    visit.paid_at = now_ist()
    visit.balance_due = round(max(visit.grand_total - new_paid, 0), 2)
    visit.payment_status = "paid" if visit.balance_due <= 0 else "partial"
    return txn


def payment_history_rows(db: Session, visit_id: int) -> list[dict]:
    rows = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.visit_id == visit_id)
        .order_by(PaymentTransaction.paid_at.asc())
        .all()
    )
    return [
        {
            "date": r.paid_at.strftime("%d %b %Y") if r.paid_at else "",
            "mode": r.payment_mode,
            "ref": r.transaction_reference or "—",
            "amount": r.amount,
        }
        for r in rows
    ]


def normalize_aadhaar(value: str) -> str:
    return value.replace(" ", "").replace("-", "").strip()