"""Receptionist module — orchestrates queue workflows; reuses existing queue services."""
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, case, cast, exists, func, or_
from sqlalchemy.orm import Session

from Models.doctor_patient_queue import PatientQueue, QueueStatus
from Models.doctor_queue_next_request import DoctorQueueNextRequest, NextRequestStatus
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import Patient
from Models.user import User
from Services import doctor_helpers as h
from Services import opd_helpers
from Services.doctor_patient_queue_service import (
    add_patient_to_queue_service,
    generate_token_number_service,
)
from Services.doctor_queue_next_service import (
    fulfill_call_patient,
    list_pending_next_requests_service,
)
from Services.queue_helpers import (
    NO_SHOW_ELIGIBLE,
    appointment_status_value,
    is_queue_status,
    persist,
    status_value,
)

IST = opd_helpers.IST

_QUEUE_ATTENTION_ORDER = case(
    (PatientQueue.status == QueueStatus.CALLED, 1),
    (PatientQueue.status == QueueStatus.WAITING, 2),
    (PatientQueue.status == QueueStatus.VITALS_COMPLETED, 2),
    else_=99,
)


def _today():
    return opd_helpers.today_ist_date()


def _called_by_name_map(db: Session, queues: list[PatientQueue]) -> dict[int, str]:
    ids = {q.called_by for q in queues if q.called_by}
    if not ids:
        return {}
    return {
        u.id: h.display_name(u.first_name, u.last_name)
        for u in db.query(User).filter(User.id.in_(ids)).all()
    }


def _queue_to_dict(
    row: PatientQueue,
    *,
    doctor_name: str | None = None,
    called_by_name: str | None = None,
) -> dict:
    data = {
        "queue_id": row.id,
        "appointment_id": row.appointment_id,
        "appointment_uid": row.appointment_uid,
        "queue_number": row.token_number,
        "patient_id": row.patient_id,
        "patient_name": row.patient_name,
        "patient_uid": row.patient_uhid,
        "patient_phone": row.patient_phone,
        "doctor_id": row.doctor_id,
        "status": status_value(row.status),
        "checked_in_at": row.queue_entered_at,
        "called_at": row.called_at,
        "called_by": row.called_by,
        "called_by_name": called_by_name,
        "consultation_started_at": row.consultation_started_at,
        "consultation_completed_at": row.consultation_completed_at,
        "queue_date": row.queue_date,
    }
    if doctor_name is not None:
        data["doctor_name"] = doctor_name
    return data


def _today_range() -> tuple[datetime, datetime]:
    start = opd_helpers.today_start_ist()
    return start, start + timedelta(days=1)


def _paginate(query, page: int, limit: int):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    total = query.count()
    rows = query.offset((page - 1) * limit).limit(limit).all()
    return rows, total, page, limit


def _queue_search_filter(term: str, *, include_doctor: bool = False):
    """Match patient name, UID, phone, token, patient_id, appointment_uid; optionally doctor name."""
    pattern = f"%{term.strip()}%"
    clauses = [
        PatientQueue.patient_name.ilike(pattern),
        PatientQueue.patient_uhid.ilike(pattern),
        PatientQueue.patient_phone.ilike(pattern),
        PatientQueue.appointment_uid.ilike(pattern),
        cast(PatientQueue.token_number, String).ilike(pattern),
        cast(PatientQueue.patient_id, String).ilike(pattern),
    ]
    if include_doctor:
        clauses.extend(
            [
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            ]
        )
    return or_(*clauses)


def _doctor_name_filter(doctor_name: str):
    pattern = f"%{doctor_name.strip()}%"
    return or_(
        User.first_name.ilike(pattern),
        User.last_name.ilike(pattern),
    )


def _appointment_query_for_today(db: Session, *, doctor_id: Optional[int] = None):
    day_start, day_end = _today_range()
    q = db.query(Appointment).filter(
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at < day_end,
    )
    if doctor_id:
        q = q.filter(Appointment.doctor_id == doctor_id)
    return q


def _queue_query_for_today(db: Session, *, doctor_id: Optional[int] = None):
    q = db.query(PatientQueue).filter(PatientQueue.queue_date == _today())
    if doctor_id:
        q = q.filter(PatientQueue.doctor_id == doctor_id)
    return q


def _average_waiting_minutes(db: Session, *, doctor_id: Optional[int] = None) -> float | None:
    q = _queue_query_for_today(db, doctor_id=doctor_id).filter(
        PatientQueue.consultation_started_at.isnot(None),
        PatientQueue.queue_entered_at.isnot(None),
    )
    avg_seconds = q.with_entities(
        func.avg(
            func.extract("epoch", PatientQueue.consultation_started_at)
            - func.extract("epoch", PatientQueue.queue_entered_at)
        )
    ).scalar()
    if avg_seconds is None:
        return None
    return round(float(avg_seconds) / 60, 2)


def get_dashboard(db: Session, *, doctor_id: Optional[int] = None) -> dict:
    today = _today()
    queue_base = _queue_query_for_today(db, doctor_id=doctor_id)
    apt_base = _appointment_query_for_today(db, doctor_id=doctor_id)

    pending_q = db.query(DoctorQueueNextRequest).filter(
        DoctorQueueNextRequest.request_date == today,
        DoctorQueueNextRequest.status == NextRequestStatus.pending.value,
    )
    if doctor_id:
        pending_q = pending_q.filter(DoctorQueueNextRequest.doctor_id == doctor_id)

    return {
        "total_patients": queue_base.count(),
        "waiting": queue_base.filter(PatientQueue.status == QueueStatus.WAITING).count(),
        "called": queue_base.filter(PatientQueue.status == QueueStatus.CALLED).count(),
        "in_progress": queue_base.filter(PatientQueue.status == QueueStatus.IN_PROGRESS).count(),
        "completed": queue_base.filter(PatientQueue.status == QueueStatus.COMPLETED).count(),
        "no_show": queue_base.filter(PatientQueue.status == QueueStatus.NO_SHOW).count(),
        "pending_doctor_requests": pending_q.count(),
        "todays_arrivals": apt_base.count(),
        "todays_checked_in": queue_base.count(),
        "todays_cancelled": apt_base.filter(
            Appointment.status == AppointmentStatus.cancelled
        ).count(),
        "average_waiting_time_minutes": _average_waiting_minutes(db, doctor_id=doctor_id),
    }


def get_arrivals(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    day_start, day_end = _today_range()
    queue_exists = exists().where(PatientQueue.appointment_id == Appointment.id)

    q = (
        db.query(Appointment, Patient, User)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(User, Appointment.doctor_id == User.id)
        .filter(
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at < day_end,
            Appointment.status == AppointmentStatus.scheduled,
            ~queue_exists,
        )
    )
    if doctor_id:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                Patient.phone.ilike(term),
                Appointment.appointment_uid.ilike(term),
            )
        )
    q = q.order_by(Appointment.scheduled_at.asc())
    rows, total, page, limit = _paginate(q, page, limit)

    arrivals = [
        {
            "appointment_id": apt.id,
            "appointment_uid": apt.appointment_uid,
            "patient_id": patient.id,
            "patient_name": h.display_name(patient.first_name, patient.last_name),
            "patient_uid": patient.patient_uid,
            "patient_phone": patient.phone,
            "doctor_id": apt.doctor_id,
            "doctor_name": opd_helpers.display_name(
                doctor.first_name, doctor.last_name, prefix="Dr. "
            ),
            "scheduled_at": apt.scheduled_at.isoformat() if apt.scheduled_at else "",
        }
        for apt, patient, doctor in rows
    ]
    return {"total": total, "page": page, "limit": limit, "arrivals": arrivals}


def check_in_patient(db: Session, appointment_id: int, *, handled_by: int | None = None) -> dict:
    queue = add_patient_to_queue_service(db, appointment_id, created_by=handled_by)
    return _queue_to_dict(queue)


def get_today_queue(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    status: QueueStatus | None = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """All patients checked in today (all doctors), from patient_queue."""
    today = _today()
    q = (
        db.query(PatientQueue, User)
        .outerjoin(User, PatientQueue.doctor_id == User.id)
        .filter(PatientQueue.queue_date == today)
        .order_by(
            PatientQueue.priority.desc(),
            _QUEUE_ATTENTION_ORDER.asc(),
            PatientQueue.token_number.asc(),
        )
    )
    if doctor_id:
        q = q.filter(PatientQueue.doctor_id == doctor_id)
    if doctor_name:
        q = q.filter(_doctor_name_filter(doctor_name))
    if patient_id is not None:
        q = q.filter(PatientQueue.patient_id == patient_id)
    if status is not None:
        q = q.filter(PatientQueue.status == status)
    if search:
        q = q.filter(_queue_search_filter(search, include_doctor=True))

    rows, total, page, limit = _paginate(q, page, limit)
    called_names = _called_by_name_map(db, [queue for queue, _ in rows])
    return {
        "queue_date": today,
        "total": total,
        "page": page,
        "limit": limit,
        "queue": [
            _queue_to_dict(
                queue,
                doctor_name=opd_helpers.display_name(doc.first_name, doc.last_name, prefix="Dr. ")
                if doc
                else None,
                called_by_name=called_names.get(queue.called_by),
            )
            for queue, doc in rows
        ],
    }


def get_doctor_queue(
    db: Session,
    doctor_id: int,
    *,
    status: QueueStatus | None = None,
    search: Optional[str] = None,
    queue_date: Optional[date] = None,
    page: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    target_date = queue_date or _today()
    q = (
        db.query(PatientQueue)
        .filter(
            PatientQueue.doctor_id == doctor_id,
            PatientQueue.queue_date == target_date,
        )
        .order_by(
            PatientQueue.priority.desc(),
            _QUEUE_ATTENTION_ORDER.asc(),
            PatientQueue.token_number.asc(),
        )
    )
    if status is not None:
        q = q.filter(PatientQueue.status == status)
    if search:
        q = q.filter(_queue_search_filter(search))

    if page is not None and limit is not None:
        rows, total, page, limit = _paginate(q, page, limit)
    else:
        rows = q.all()
        total, page, limit = len(rows), 1, len(rows) or 1

    called_names = _called_by_name_map(db, rows)
    return {
        "doctor_id": doctor_id,
        "total": total,
        "page": page,
        "limit": limit,
        "queue": [
            _queue_to_dict(r, called_by_name=called_names.get(r.called_by)) for r in rows
        ],
    }


def get_pending_calls(db: Session, *, doctor_id: Optional[int] = None) -> dict:
    rows = list_pending_next_requests_service(db, doctor_id=doctor_id)
    return {"total": len(rows), "pending_calls": rows}


def call_patient(db: Session, queue_id: int, handled_by: int) -> dict:
    queue = fulfill_call_patient(
        db, queue_id, handled_by, require_pending_request=True
    )
    called_names = _called_by_name_map(db, [queue])
    return _queue_to_dict(queue, called_by_name=called_names.get(queue.called_by))


def mark_no_show(db: Session, queue_id: int, *, handled_by: int | None = None) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if not is_queue_status(queue.status, NO_SHOW_ELIGIBLE):
        raise HTTPException(
            status_code=400,
            detail=(
                "No-show is only allowed for patients waiting or called in the queue "
                f"(current: {status_value(queue.status)})"
            ),
        )

    queue.status = QueueStatus.NO_SHOW
    queue.called_at = None
    queue.called_by = None
    if handled_by:
        queue.updated_by = handled_by

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment and appointment_status_value(appointment.status) not in (
        AppointmentStatus.completed.value,
        AppointmentStatus.cancelled.value,
    ):
        appointment.status = AppointmentStatus.cancelled

    (
        db.query(DoctorQueueNextRequest)
        .filter(
            DoctorQueueNextRequest.appointment_id == queue.appointment_id,
            DoctorQueueNextRequest.doctor_id == queue.doctor_id,
            DoctorQueueNextRequest.request_date == queue.queue_date,
            DoctorQueueNextRequest.status == NextRequestStatus.pending.value,
        )
        .update(
            {"status": NextRequestStatus.cancelled.value},
            synchronize_session=False,
        )
    )

    persist(db)
    db.refresh(queue)
    return _queue_to_dict(queue)


def rejoin_queue(db: Session, queue_id: int, *, handled_by: int | None = None) -> dict:
    queue = (
        db.query(PatientQueue)
        .filter(PatientQueue.id == queue_id)
        .with_for_update()
        .first()
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if status_value(queue.status) != QueueStatus.NO_SHOW.value:
        raise HTTPException(
            status_code=400,
            detail="Only no-show patients can rejoin the queue",
        )

    queue.status = QueueStatus.WAITING
    queue.token_number = generate_token_number_service(db, queue.doctor_id)
    queue.called_at = None
    queue.called_by = None
    queue.consultation_started_at = None
    queue.consultation_completed_at = None
    if handled_by:
        queue.updated_by = handled_by

    appointment = db.query(Appointment).filter(Appointment.id == queue.appointment_id).first()
    if appointment and appointment_status_value(appointment.status) != AppointmentStatus.completed.value:
        appointment.status = AppointmentStatus.waiting

    persist(db)
    db.refresh(queue)
    return _queue_to_dict(queue)


def _queue_history_query(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: QueueStatus | None = None,
    search: Optional[str] = None,
):
    if single_date:
        date_from = date_to = single_date
    if not date_from:
        date_from = _today()
    if not date_to:
        date_to = date_from

    q = (
        db.query(PatientQueue, User)
        .outerjoin(User, PatientQueue.doctor_id == User.id)
        .filter(
            PatientQueue.queue_date >= date_from,
            PatientQueue.queue_date <= date_to,
        )
        .order_by(PatientQueue.queue_date.desc(), PatientQueue.token_number.asc())
    )
    if doctor_id:
        q = q.filter(PatientQueue.doctor_id == doctor_id)
    if status is not None:
        q = q.filter(PatientQueue.status == status)
    if search:
        q = q.filter(_queue_search_filter(search, include_doctor=True))
    return q, date_from, date_to


def get_queue_history(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: QueueStatus | None = None,
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
        search=search,
    )

    rows, total, page, limit = _paginate(q, page, limit)
    called_names = _called_by_name_map(db, [queue for queue, _ in rows])
    history = [
        _queue_to_dict(
            queue,
            doctor_name=opd_helpers.display_name(doc.first_name, doc.last_name, prefix="Dr. ")
            if doc
            else None,
            called_by_name=called_names.get(queue.called_by),
        )
        for queue, doc in rows
    ]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total": total,
        "page": page,
        "limit": limit,
        "history": history,
    }


_EXPORT_COLUMNS = [
    ("queue_date", "Queue Date"),
    ("queue_number", "Token"),
    ("appointment_uid", "Appointment UID"),
    ("patient_name", "Patient"),
    ("patient_uid", "UHID"),
    ("patient_phone", "Phone"),
    ("doctor_name", "Doctor"),
    ("status", "Status"),
    ("checked_in_at", "Checked In"),
    ("called_at", "Called At"),
    ("called_by", "Called By (ID)"),
    ("called_by_name", "Called By (Name)"),
    ("consultation_started_at", "Consultation Started"),
    ("consultation_completed_at", "Consultation Completed"),
]


def export_queue_history_csv(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: QueueStatus | None = None,
    search: Optional[str] = None,
) -> tuple[str, str]:
    q, date_from, date_to = _queue_history_query(
        db,
        single_date=single_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        status=status,
        search=search,
    )
    rows = q.all()
    called_names = _called_by_name_map(db, [queue for queue, _ in rows])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in _EXPORT_COLUMNS])

    for queue, doc in rows:
        item = _queue_to_dict(
            queue,
            doctor_name=opd_helpers.display_name(doc.first_name, doc.last_name, prefix="Dr. ")
            if doc
            else None,
            called_by_name=called_names.get(queue.called_by),
        )
        writer.writerow(
            [
                item.get(key) if item.get(key) is not None else ""
                for key, _ in _EXPORT_COLUMNS
            ]
        )

    filename = f"queue-history-{date_from.isoformat()}"
    if date_to != date_from:
        filename += f"-to-{date_to.isoformat()}"
    filename += ".csv"
    return buffer.getvalue(), filename
