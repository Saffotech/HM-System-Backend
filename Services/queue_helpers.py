"""Shared queue status helpers — single source of truth for queue workflow code."""
from enum import Enum

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import QueueStatus
from Models.doctor_queue_next_request import NextRequestStatus
from Models.opd_billing import AppointmentStatus

READY_FOR_DOCTOR = frozenset({QueueStatus.WAITING, QueueStatus.VITALS_COMPLETED})
NO_SHOW_ELIGIBLE = frozenset(
    {QueueStatus.WAITING, QueueStatus.VITALS_COMPLETED, QueueStatus.CALLED}
)
START_CONSULTATION_ELIGIBLE = frozenset(
    {
        QueueStatus.WAITING,
        QueueStatus.VITALS_COMPLETED,
        QueueStatus.CALLED,
        QueueStatus.IN_PROGRESS,
    }
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
    "START_CONSULTATION_ELIGIBLE",
    "REQUEST_NEXT_APPOINTMENT_STATUSES",
    "status_value",
    "appointment_status_value",
    "is_queue_status",
    "is_appointment_status",
    "queue_status_from_query",
    "persist",
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
