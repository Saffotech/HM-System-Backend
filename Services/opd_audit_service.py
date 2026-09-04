"""Audit logging for OPD-module actions (Super Admin reads via GET /super-admin/audit)."""
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


# ── Priority 1: patient / visit / bill ─────────────────────────


def log_patient_register(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
    payment_mode: Optional[str] = None,
    pay_later: bool = False,
) -> None:
    patient_id = _attr(result, "patient_id")
    patient_uid = _attr(result, "patient_uid")
    visit_id = _attr(result, "visit_id")
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.patient.register",
        resource_type="opd_patient",
        resource_id=patient_id,
        summary=(
            f"OPD patient {patient_uid or patient_id} registered"
            + (f" bill={bill_number}" if bill_number else "")
        ),
        details={
            "patient_id": patient_id,
            "patient_uid": patient_uid,
            "visit_id": visit_id,
            "bill_number": bill_number,
            "token_number": _attr(result, "token_number"),
            "appointment_id": _attr(result, "appointment_id"),
            "payment_mode": payment_mode,
            "pay_later": pay_later,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_patient_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_id: int,
    result: Any,
    changes: Optional[dict[str, Any]] = None,
) -> None:
    changed_keys = list(changes.keys()) if changes else None
    _log(
        db,
        actor=actor,
        action="opd.patient.update",
        resource_type="opd_patient",
        resource_id=patient_id,
        summary=f"OPD patient {_attr(result, 'patient_uid') or patient_id} updated",
        details={
            "patient_id": patient_id,
            "patient_uid": _attr(result, "patient_uid"),
            "changed_fields": changed_keys,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_patient_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="opd.patient.delete",
        resource_type="opd_patient",
        resource_id=patient_id,
        summary=(
            f"OPD patient {_attr(result, 'patient_uid') or patient_id} deactivated"
        ),
        details={
            "patient_id": patient_id,
            "patient_uid": _attr(result, "patient_uid"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_visit_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
    payment_mode: Optional[str] = None,
    pay_later: bool = False,
) -> None:
    visit_id = _attr(result, "visit_id")
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.visit.create",
        resource_type="opd_visit",
        resource_id=visit_id,
        summary=(
            f"OPD visit {visit_id} created"
            + (f" bill={bill_number}" if bill_number else "")
        ),
        details={
            "visit_id": visit_id,
            "patient_id": _attr(result, "patient_id"),
            "patient_uid": _attr(result, "patient_uid"),
            "bill_number": bill_number,
            "token_number": _attr(result, "token_number"),
            "grand_total": _attr(result, "grand_total"),
            "payment_status": _attr(result, "payment_status"),
            "appointment_id": _attr(result, "appointment_id"),
            "payment_mode": payment_mode,
            "pay_later": pay_later,
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
    visit_id = _attr(result, "visit_id")
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.bill.generate",
        resource_type="opd_visit",
        resource_id=visit_id,
        summary=(
            f"OPD bill {bill_number or visit_id} generated "
            f"for patient {_attr(result, 'patient_id')}"
        ),
        details={
            "visit_id": visit_id,
            "patient_id": _attr(result, "patient_id"),
            "patient_uid": _attr(result, "patient_uid"),
            "bill_number": bill_number,
            "token_number": _attr(result, "token_number"),
            "grand_total": _attr(result, "grand_total"),
            "payment_status": _attr(result, "payment_status"),
            "appointment_id": _attr(result, "appointment_id"),
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
    visit_id: int,
    result: Any,
    amount: Optional[float] = None,
    payment_mode: Optional[str] = None,
) -> None:
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.bill.pay",
        resource_type="opd_visit",
        resource_id=visit_id,
        summary=(
            f"OPD payment on bill {bill_number or visit_id}"
            + (f" amount={amount}" if amount is not None else "")
        ),
        details={
            "visit_id": visit_id,
            "bill_number": bill_number,
            "patient_id": _attr(result, "patient_id"),
            "patient_uid": _attr(result, "patient_uid"),
            "amount": amount if amount is not None else _attr(result, "amount_paid"),
            "payment_mode": payment_mode,
            "total_paid": _attr(result, "total_paid"),
            "balance_due": _attr(result, "balance_due"),
            "payment_status": _attr(result, "payment_status"),
            "appointment_id": _attr(result, "appointment_id"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bill_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    result: Any,
    changes: Optional[dict[str, Any]] = None,
) -> None:
    changed_keys = list(changes.keys()) if changes else None
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.bill.update",
        resource_type="opd_visit",
        resource_id=visit_id,
        summary=f"OPD bill {bill_number or visit_id} updated",
        details={
            "visit_id": visit_id,
            "bill_number": bill_number,
            "patient_id": _attr(result, "patient_id"),
            "patient_uid": _attr(result, "patient_uid"),
            "grand_total": _attr(result, "grand_total"),
            "balance_due": _attr(result, "balance_due"),
            "payment_status": _attr(result, "payment_status"),
            "changed_fields": changed_keys,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_bill_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    result: Any,
) -> None:
    bill_number = _attr(result, "bill_number")
    _log(
        db,
        actor=actor,
        action="opd.bill.delete",
        resource_type="opd_visit",
        resource_id=visit_id,
        summary=f"OPD bill {bill_number or visit_id} cancelled",
        details={
            "visit_id": visit_id,
            "bill_number": bill_number,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ── Priority 2: appointments ───────────────────────────────────


def log_appointment_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    appointment_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="opd.appointment.create",
        resource_type="opd_appointment",
        resource_id=appointment_id,
        summary=(
            f"OPD appointment {_attr(result, 'appointment_uid') or appointment_id} "
            f"booked for patient {_attr(result, 'patient_id')}"
        ),
        details={
            "appointment_id": appointment_id,
            "appointment_uid": _attr(result, "appointment_uid"),
            "patient_id": _attr(result, "patient_id"),
            "patient_uid": _attr(result, "patient_uid"),
            "doctor_id": _attr(result, "doctor_id"),
            "department_id": _attr(result, "department_id"),
            "scheduled_at": _attr(result, "scheduled_at"),
            "status": _attr(result, "status"),
            "appointment_type": _attr(result, "appointment_type"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_appointment_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    appointment_id: int,
    result: Any,
    changes: Optional[dict[str, Any]] = None,
) -> None:
    changed = dict(changes) if changes else {}
    if "scheduled_at" in changed and changed["scheduled_at"] is not None:
        val = changed["scheduled_at"]
        changed["scheduled_at"] = val.isoformat() if hasattr(val, "isoformat") else str(val)
    _log(
        db,
        actor=actor,
        action="opd.appointment.update",
        resource_type="opd_appointment",
        resource_id=appointment_id,
        summary=(
            f"OPD appointment {_attr(result, 'appointment_uid') or appointment_id} updated"
        ),
        details={
            "appointment_id": appointment_id,
            "appointment_uid": _attr(result, "appointment_uid"),
            "patient_id": _attr(result, "patient_id"),
            "doctor_id": _attr(result, "doctor_id"),
            "department_id": _attr(result, "department_id"),
            "scheduled_at": _attr(result, "scheduled_at"),
            "status": _attr(result, "status"),
            "changes": changed or None,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_appointment_cancel(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    appointment_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="opd.appointment.cancel",
        resource_type="opd_appointment",
        resource_id=appointment_id,
        summary=(
            f"OPD appointment {_attr(result, 'appointment_uid') or appointment_id} cancelled"
        ),
        details={
            "appointment_id": appointment_id,
            "appointment_uid": _attr(result, "appointment_uid"),
            "patient_id": _attr(result, "patient_id"),
            "doctor_id": _attr(result, "doctor_id"),
            "scheduled_at": _attr(result, "scheduled_at"),
            "status": _attr(result, "status"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_appointment_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    appointment_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="opd.appointment.delete",
        resource_type="opd_appointment",
        resource_id=appointment_id,
        summary=f"OPD appointment {appointment_id} deleted",
        details={
            "appointment_id": appointment_id,
            "message": _attr(result, "message"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
