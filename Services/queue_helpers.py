"""Shared queue status helpers — single source of truth for queue workflow code."""
from enum import Enum

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import QueueStatus
from Models.doctor_queue_next_request import NextRequestStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit

READY_FOR_DOCTOR = frozenset({QueueStatus.WAITING, QueueStatus.VITALS_COMPLETED})
NO_SHOW_ELIGIBLE = frozenset({QueueStatus.WAITING, QueueStatus.VITALS_COMPLETED})
COMPLETE_CONSULTATION_ELIGIBLE = frozenset(
    {QueueStatus.WAITING, QueueStatus.VITALS_COMPLETED}
)

REQUEST_NEXT_APPOINTMENT_STATUSES = frozenset(
    {AppointmentStatus.scheduled, AppointmentStatus.waiting}
)

__all__ = [
    "AppointmentStatus",
    "NextRequestStatus",
    "QueueStatus",
    "READY_FOR_DOCTOR",
    "NO_SHOW_ELIGIBLE",
    "COMPLETE_CONSULTATION_ELIGIBLE",
    "REQUEST_NEXT_APPOINTMENT_STATUSES",
    "status_value",
    "appointment_status_value",
    "is_queue_status",
    "is_appointment_status",
    "queue_status_from_query",
    "persist",
    "is_visit_paid",
    "is_appointment_active",
    "apply_eligible_queue_filters",
    "apply_receptionist_payment_filter",
    "is_visit_unpaid_sql",
    "is_visit_paid_sql",
    "receptionist_payment_filter_from_query",
]


def status_value(status) -> str:
    if isinstance(status, Enum):
        return status.value
    return status


def appointment_status_value(status) -> str:
    if isinstance(status, AppointmentStatus):
        return status.value
    if isinstance(status, str):
        return status
    return status_value(status)


def is_queue_status(status, allowed: frozenset[QueueStatus]) -> bool:
    raw = status_value(status)
    return any(raw == item.value for item in allowed)


def is_appointment_status(status, allowed: frozenset[AppointmentStatus]) -> bool:
    raw = appointment_status_value(status)
    return any(raw == item.value for item in allowed)


def queue_status_from_query(value: str | None) -> QueueStatus | None:
    if value is None:
        return None
    try:
        return QueueStatus(value)
    except ValueError as exc:
        allowed = ", ".join(s.value for s in QueueStatus)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid queue status '{value}'. Use one of: {allowed}",
        ) from exc


def persist(db: Session, *, commit: bool = True) -> None:
    if commit:
        db.commit()
    else:
        db.flush()


def is_visit_paid(visit: OpdVisit) -> bool:
    """Paid in full, or no payment required (zero total)."""
    if visit.payment_status == "paid":
        return True
    if (visit.grand_total or 0) <= 0:
        return True
    return False


def is_appointment_active(appointment: Appointment) -> bool:
    return appointment_status_value(appointment.status) != AppointmentStatus.cancelled.value


def apply_eligible_queue_filters(query):
    """
    Doctor queue views: paid visit + active appointment.
    Query must already join Appointment and OpdVisit on appointment_id.
    """
    return query.filter(
        OpdVisit.payment_status == "paid",
        Appointment.status != AppointmentStatus.cancelled,
    )


def is_visit_paid_sql(visit_model=OpdVisit):
    """SQL expression matching is_visit_paid() for OpdVisit rows."""
    return or_(
        visit_model.payment_status == "paid",
        func.coalesce(visit_model.grand_total, 0) <= 0,
    )


def is_visit_unpaid_sql(visit_model=OpdVisit):
    """SQL expression for unpaid visits (no visit row also counts as unpaid)."""
    return or_(
        visit_model.id.is_(None),
        and_(
            visit_model.payment_status.in_(["pending", "partial"]),
            func.coalesce(visit_model.grand_total, 0) > 0,
        ),
    )


def receptionist_payment_filter_from_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"paid", "unpaid"}:
        return normalized
    raise HTTPException(
        status_code=422,
        detail="Invalid payment_status filter. Use 'paid' or 'unpaid'.",
    )


def apply_receptionist_payment_filter(
    query,
    payment_filter: str | None,
    *,
    visit_model=OpdVisit,
):
    """
    Receptionist appointment views: optional paid/unpaid filter.
    Query must already outerjoin OpdVisit (or an alias) on appointment_id.
    """
    if payment_filter is None:
        return query
    if payment_filter == "paid":
        return query.filter(
            visit_model.id.isnot(None),
            is_visit_paid_sql(visit_model),
        )
    if payment_filter == "unpaid":
        return query.filter(is_visit_unpaid_sql(visit_model))
    return query
