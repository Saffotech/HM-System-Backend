"""Receptionist module — view-only appointment boards (scheduled / completed)."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session, aliased

from Models.doctor_patient_queue import PatientQueue
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Services import doctor_helpers as dh
from Services import opd_helpers
from Services.queue_helpers import apply_receptionist_payment_filter, status_value

IST = opd_helpers.IST


def receptionist_appointment_status_from_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"scheduled", "completed"}:
        return normalized
    raise HTTPException(
        status_code=422,
        detail="Invalid status filter. Use 'scheduled' or 'completed'.",
    )


def _receptionist_display_status(appointment: Appointment) -> str:
    if status_value(appointment.status) == AppointmentStatus.completed.value:
        return "completed"
    return "scheduled"


def _apply_receptionist_status_filter(query, status: str | None):
    if status is None:
        return query
    if status == "completed":
        return query.filter(Appointment.status == AppointmentStatus.completed)
    if status == "scheduled":
        return query.filter(Appointment.status != AppointmentStatus.completed)
    return query


def _today():
    return opd_helpers.today_ist_date()


def _resolve_payment_status(visit: OpdVisit | None) -> str:
    if visit is None:
        return "pending"
    return visit.payment_status or "pending"


def _appointment_row_to_dict(
    appointment: Appointment,
    patient: Patient,
    visit: OpdVisit | None,
    queue: PatientQueue | None,
    *,
    doctor_name: str | None = None,
    queue_date: date | None = None,
) -> dict:
    data = {
        "appointment_id": appointment.id,
        "appointment_uid": appointment.appointment_uid,
        "patient_id": patient.id,
        "patient_name": opd_helpers.display_name(patient.first_name, patient.last_name),
        "patient_uid": patient.patient_uid,
        "patient_phone": patient.phone,
        "doctor_id": appointment.doctor_id,
        "status": _receptionist_display_status(appointment),
        "payment_status": _resolve_payment_status(visit),
        "checked_in_at": queue.queue_entered_at if queue else None,
        "called_at": queue.called_at if queue else None,
        "consultation_started_at": queue.consultation_started_at if queue else None,
        "consultation_completed_at": queue.consultation_completed_at if queue else None,
        "queue_date": queue.queue_date if queue else queue_date,
    }
    if doctor_name is not None:
        data["doctor_name"] = doctor_name
    return data


def _latest_visit_subquery(db: Session):
    return (
        db.query(
            OpdVisit.appointment_id.label("appointment_id"),
            func.max(OpdVisit.id).label("visit_id"),
        )
        .filter(OpdVisit.appointment_id.isnot(None))
        .group_by(OpdVisit.appointment_id)
        .subquery()
    )


def _receptionist_appointments_query(
    db: Session,
    *,
    date_from: date,
    date_to: date | None = None,
    doctor_id: Optional[int] = None,
    payment_filter: Optional[str] = None,
    include_doctor_join: bool = False,
):
    """Appointments in range with latest visit and optional queue row for that day."""
    date_to = date_to or date_from
    range_start = datetime.combine(date_from, time.min, tzinfo=IST)
    range_end = datetime.combine(date_to, time.max, tzinfo=IST)
    latest_visit = _latest_visit_subquery(db)
    Visit = aliased(OpdVisit)

    q = (
        db.query(Appointment, Patient, Visit, PatientQueue, User)
        .join(Patient, Appointment.patient_id == Patient.id)
        .outerjoin(latest_visit, latest_visit.c.appointment_id == Appointment.id)
        .outerjoin(Visit, Visit.id == latest_visit.c.visit_id)
        .outerjoin(
            PatientQueue,
            and_(
                PatientQueue.appointment_id == Appointment.id,
                PatientQueue.queue_date
                == func.date(func.timezone("Asia/Kolkata", Appointment.scheduled_at)),
            ),
        )
        .outerjoin(User, Appointment.doctor_id == User.id)
        .filter(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at <= range_end,
            Appointment.status != AppointmentStatus.cancelled,
        )
    )
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    q = apply_receptionist_payment_filter(q, payment_filter)
    return q


def _appointment_search_filter(term: str, *, include_doctor: bool = False):
    pattern = f"%{term.strip()}%"
    clauses = [
        Patient.first_name.ilike(pattern),
        Patient.last_name.ilike(pattern),
        Patient.patient_uid.ilike(pattern),
        Patient.phone.ilike(pattern),
        Appointment.appointment_uid.ilike(pattern),
        cast(Appointment.id, String).ilike(pattern),
        cast(Patient.id, String).ilike(pattern),
    ]
    if include_doctor:
        clauses.extend(
            [
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            ]
        )
    return or_(*clauses)


def _appointment_list_order():
    return (Appointment.scheduled_at.asc(),)


def _today_range() -> tuple[datetime, datetime]:
    start = opd_helpers.today_start_ist()
    return start, start + timedelta(days=1)


def _paginate(query, page: int, limit: int):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    total = query.count()
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return rows, total, page, limit


def _doctor_name_filter(doctor_name: str):
    pattern = f"%{doctor_name.strip()}%"
    return or_(
        User.first_name.ilike(pattern),
        User.last_name.ilike(pattern),
    )


def _todays_appointments_query(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    payment_filter: Optional[str] = None,
):
    today = _today()
    return _receptionist_appointments_query(
        db,
        date_from=today,
        date_to=today,
        doctor_id=doctor_id,
        payment_filter=payment_filter,
    )


def get_dashboard(db: Session, *, doctor_id: Optional[int] = None) -> dict:
    all_appointments = _todays_appointments_query(db, doctor_id=doctor_id)
    paid_appointments = _todays_appointments_query(db, doctor_id=doctor_id, payment_filter="paid")
    unpaid_appointments = _todays_appointments_query(db, doctor_id=doctor_id, payment_filter="unpaid")
    completed_appointments = _apply_receptionist_status_filter(
        _todays_appointments_query(db, doctor_id=doctor_id),
        "completed",
    )

    return {
        "total_patients": all_appointments.count(),
        "completed": completed_appointments.count(),
        "todays_paid_appointments": paid_appointments.count(),
        "todays_unpaid_appointments": unpaid_appointments.count(),
        "todays_cancelled": (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= _today_range()[0],
                Appointment.scheduled_at < _today_range()[1],
                Appointment.status == AppointmentStatus.cancelled,
            )
            .count()
            if not doctor_id
            else db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= _today_range()[0],
                Appointment.scheduled_at < _today_range()[1],
                Appointment.status == AppointmentStatus.cancelled,
                Appointment.doctor_id == doctor_id,
            )
            .count()
        ),
    }


def get_today_queue(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Today's appointments (paid and unpaid); optional appointment status and payment filters."""
    today = _today()
    q = _todays_appointments_query(
        db, doctor_id=doctor_id, payment_filter=payment_filter
    ).order_by(*_appointment_list_order())
    if doctor_name:
        q = q.filter(_doctor_name_filter(doctor_name))
    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))

    rows, total, page, limit = _paginate(q, page, limit)
    return {
        "queue_date": today,
        "total": total,
        "page": page,
        "limit": limit,
        "queue": [
            _appointment_row_to_dict(
                appointment,
                patient,
                visit,
                queue,
                doctor_name=opd_helpers.display_name(doc.first_name, doc.last_name, prefix="Dr. ")
                if doc
                else None,
                queue_date=today,
            )
            for appointment, patient, visit, queue, doc in rows
        ],
    }


def get_doctor_queue(
    db: Session,
    doctor_id: int,
    *,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    queue_date: Optional[date] = None,
    page: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    target_date = queue_date or _today()
    q = _receptionist_appointments_query(
        db,
        date_from=target_date,
        date_to=target_date,
        doctor_id=doctor_id,
        payment_filter=payment_filter,
    ).order_by(*_appointment_list_order())
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search))

    if page is not None and limit is not None:
        rows, total, page, limit = _paginate(q, page, limit)
    else:
        rows = q.all()
        total, page, limit = len(rows), 1, len(rows) or 1

    return {
        "doctor_id": doctor_id,
        "total": total,
        "page": page,
        "limit": limit,
        "queue": [
            _appointment_row_to_dict(
                appointment,
                patient,
                visit,
                queue,
                queue_date=target_date,
            )
            for appointment, patient, visit, queue, _doc in rows
        ],
    }


def _queue_history_query(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
):
    if single_date:
        date_from = date_to = single_date
    if not date_from:
        date_from = _today()
    if not date_to:
        date_to = date_from

    q = _receptionist_appointments_query(
        db,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        payment_filter=payment_filter,
    ).order_by(Appointment.scheduled_at.desc())
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))
    return q, date_from, date_to


def get_queue_history(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q, date_from, date_to = _queue_history_query(
        db,
        single_date=single_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        status=status,
        payment_filter=payment_filter,
        search=search,
    )

    rows, total, page, limit = _paginate(q, page, limit)
    history = [
        _appointment_row_to_dict(
            appointment,
            patient,
            visit,
            queue,
            doctor_name=opd_helpers.display_name(doc.first_name, doc.last_name, prefix="Dr. ")
            if doc
            else None,
            queue_date=queue.queue_date if queue else appointment.scheduled_at.astimezone(IST).date(),
        )
        for appointment, patient, visit, queue, doc in rows
    ]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total": total,
        "page": page,
        "limit": limit,
        "history": history,
    }
