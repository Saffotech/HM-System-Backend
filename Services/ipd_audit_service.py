"""Audit logging for IPD-module actions (Super Admin reads via GET /super-admin/audit)."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from Models.user import User
from Services.audit_helpers import safe_log_event


def _attr(obj: Any, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _log(
    db: Session,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    summary: str,
    details: Optional[dict[str, Any]] = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ── Priority 1: admission / bed / bill ─────────────────────────


def log_admission_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    admission_id = _attr(result, "id")
    patient_id = _attr(result, "patient_id")
    admission_no = _attr(result, "admission_no")
    bed_id = _attr(result, "bed_id")
    bed_number = _attr(result, "bed_number")
    ward_name = _attr(result, "ward_name")
    _log(
        db,
        actor=actor,
        action="ipd.admission.create",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=(
            f"IPD admission {admission_no or admission_id} created "
            f"for patient {patient_id}"
        ),
        details={
            "admission_id": admission_id,
            "admission_no": admission_no,
            "patient_id": patient_id,
            "bed_id": bed_id,
            "bed_number": bed_number,
            "ward_name": ward_name,
            "doctor_id": _attr(result, "doctor_id"),
            "department_id": _attr(result, "department_id"),
            "payment_type": _attr(result, "payment_type"),
            "diagnosis": _attr(result, "diagnosis"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if bed_id is not None:
        log_bed_assign(
            db,
            actor=actor,
            ip_address=ip_address,
            user_agent=user_agent,
            admission_id=admission_id,
            patient_id=patient_id,
            bed_id=bed_id,
            bed_number=bed_number,
            ward_name=ward_name,
            source="admit",
        )


def log_admission_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
    changes: Optional[dict[str, Any]] = None,
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.admission.update",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=f"IPD admission {admission_id} updated",
        details={
            "admission_id": admission_id,
            "admission_no": _attr(result, "admission_no"),
            "patient_id": _attr(result, "patient_id"),
            "changes": changes or {},
            "doctor_id": _attr(result, "doctor_id"),
            "department_id": _attr(result, "department_id"),
            "diagnosis": _attr(result, "diagnosis"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_admission_discharge(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
) -> None:
    admission = _attr(result, "admission") or result
    bill = _attr(result, "bill")
    _log(
        db,
        actor=actor,
        action="ipd.admission.discharge",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=(
            f"IPD admission {_attr(admission, 'admission_no') or admission_id} discharged"
        ),
        details={
            "admission_id": admission_id,
            "admission_no": _attr(admission, "admission_no"),
            "patient_id": _attr(admission, "patient_id"),
            "status": _attr(admission, "status"),
            "bill_id": _attr(bill, "id"),
            "bill_number": _attr(bill, "bill_number"),
            "balance_due": _attr(bill, "balance_due"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bed_assign(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: Optional[int],
    patient_id: Optional[int],
    bed_id: Optional[int],
    bed_number: Optional[str] = None,
    ward_name: Optional[str] = None,
    source: str = "admit",
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.bed.assign",
        resource_type="bed",
        resource_id=bed_id,
        summary=(
            f"IPD bed {bed_number or bed_id} assigned "
            f"to patient {patient_id} (admission {admission_id})"
        ),
        details={
            "admission_id": admission_id,
            "patient_id": patient_id,
            "bed_id": bed_id,
            "bed_number": bed_number,
            "ward_name": ward_name,
            "source": source,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bed_transfer(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
    from_bed_id: Optional[int] = None,
    to_bed_id: Optional[int] = None,
) -> None:
    admission_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="ipd.bed.transfer",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=(
            f"IPD bed transfer for admission {admission_id}: "
            f"{from_bed_id} → {_attr(result, 'bed_id') or to_bed_id}"
        ),
        details={
            "admission_id": admission_id,
            "patient_id": _attr(result, "patient_id"),
            "from_bed_id": from_bed_id,
            "to_bed_id": _attr(result, "bed_id") or to_bed_id,
            "bed_number": _attr(result, "bed_number"),
            "ward_name": _attr(result, "ward_name"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bill_generate(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    bill_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="ipd.bill.generate",
        resource_type="ipd_bill",
        resource_id=bill_id,
        summary=(
            f"IPD bill {_attr(result, 'bill_number') or bill_id} generated "
            f"for admission {_attr(result, 'admission_id')}"
        ),
        details={
            "bill_id": bill_id,
            "bill_number": _attr(result, "bill_number"),
            "admission_id": _attr(result, "admission_id"),
            "patient_id": _attr(result, "patient_id"),
            "grand_total": _attr(result, "grand_total"),
            "balance_due": _attr(result, "balance_due"),
            "status": _attr(result, "status"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bill_pay(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    bill_id: int,
    result: Any,
    amount: Optional[float] = None,
    payment_mode: Optional[str] = None,
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.bill.pay",
        resource_type="ipd_bill",
        resource_id=bill_id,
        summary=(
            f"IPD payment recorded on bill "
            f"{_attr(result, 'bill_number') or bill_id}"
            + (f" amount={amount}" if amount is not None else "")
        ),
        details={
            "bill_id": bill_id,
            "bill_number": _attr(result, "bill_number"),
            "admission_id": _attr(result, "admission_id"),
            "patient_id": _attr(result, "patient_id"),
            "amount": amount,
            "payment_mode": payment_mode or _attr(result, "payment_mode"),
            "paid_amount": _attr(result, "paid_amount"),
            "balance_due": _attr(result, "balance_due"),
            "status": _attr(result, "status"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_billing_daily_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
) -> None:
    items = _attr(result, "daily_items") or _attr(result, "items") or []
    _log(
        db,
        actor=actor,
        action="ipd.billing.daily_update",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=f"IPD daily charges updated for admission {admission_id}",
        details={
            "admission_id": admission_id,
            "line_count": len(items) if isinstance(items, list) else None,
            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_billing_final_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.billing.final_update",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=f"IPD final hospital charges updated for admission {admission_id}",
        details={
            "admission_id": admission_id,
            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
            "totals": {
                k: _attr(result, k)
                for k in ("subtotal", "grand_total", "total", "balance_due")
                if _attr(result, k) is not None
            },
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ── Priority 2: insurance ──────────────────────────────────────


def log_insurance_claim_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    claim: Any,
) -> None:
    claim_id = _attr(claim, "id") or _attr(claim, "claim_id")
    resource_id = None
    try:
        if claim_id is not None:
            resource_id = int(claim_id)
    except (TypeError, ValueError):
        resource_id = None
    _log(
        db,
        actor=actor,
        action="ipd.insurance.claim_update",
        resource_type="ipd_insurance_claim",
        resource_id=resource_id,
        summary=f"IPD insurance claim {claim_id} updated",
        details={
            "claim_id": claim_id,
            "admission_id": _attr(claim, "admission_id"),
            "patient_id": _attr(claim, "patient_id"),
            "status": _attr(claim, "status") or _attr(claim, "claim_status"),
            "approved_amount": _attr(claim, "approved_amount"),
            "claimed_amount": _attr(claim, "claimed_amount"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_insurance_payment_add(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    claim_id: Any,
    result: Any,
    kind: str,
) -> None:
    action = (
        "ipd.insurance.payment_add"
        if kind == "insurance"
        else "ipd.insurance.patient_payment_add"
    )
    payment = (
        result.get("payment")
        if isinstance(result, dict) and "payment" in result
        else result
    )
    amount = _attr(payment, "amount") or _attr(result, "amount")
    resource_id = None
    try:
        if claim_id is not None and str(claim_id).isdigit():
            resource_id = int(claim_id)
    except (TypeError, ValueError):
        resource_id = None
    _log(
        db,
        actor=actor,
        action=action,
        resource_type="ipd_insurance_claim",
        resource_id=resource_id,
        summary=(
            f"IPD {'insurance' if kind == 'insurance' else 'patient'} payment "
            f"added on claim {claim_id}"
            + (f" amount={amount}" if amount is not None else "")
        ),
        details={
            "claim_id": claim_id,
            "kind": kind,
            "amount": amount,
            "payment_mode": _attr(payment, "payment_mode")
            or _attr(result, "payment_mode"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_insurance_admission_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.insurance.admission_update",
        resource_type="ipd_admission",
        resource_id=admission_id,
        summary=f"IPD admission {admission_id} insurance profile updated",
        details={
            "admission_id": admission_id,
            "payment_type": _attr(result, "payment_type"),
            "claim_id": _attr(result, "id") or _attr(result, "claim_id"),
            "status": _attr(result, "status") or _attr(result, "claim_status"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ── Priority 3: visit / profile ────────────────────────────────


def log_visit_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    admission_id: int,
    result: Any,
) -> None:
    visit_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="ipd.visit.create",
        resource_type="ipd_doctor_visit",
        resource_id=visit_id,
        summary=f"IPD doctor visit created on admission {admission_id}",
        details={
            "visit_id": visit_id,
            "admission_id": admission_id,
            "doctor_id": _attr(result, "doctor_id"),
            "visit_date": _attr(result, "visit_date") or _attr(result, "visited_at"),
            "notes": _attr(result, "notes"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_profile_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="ipd.profile.update",
        resource_type="ipd_profile",
        resource_id=_attr(result, "id") or actor.id,
        summary=f"IPD staff profile updated for user {actor.id}",
        details={
            "user_id": actor.id,
            "profile_id": _attr(result, "id"),
            "is_profile_completed": _attr(result, "is_profile_completed"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
