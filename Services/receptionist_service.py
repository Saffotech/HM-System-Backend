"""Receptionist module — view-only appointment boards (scheduled / completed)."""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, and_, case, cast, func, or_
from sqlalchemy.orm import Session, aliased, joinedload

from Models.department import Department
from Models.doctor_patient_queue import PatientQueue
from Models.doctor_profile import DoctorProfile
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit, Patient
from Models.role import Role
from Models.user import User
from Services import opd_helpers
from Services.queue_helpers import (
    apply_receptionist_payment_filter,
    is_visit_paid_sql,
    status_value,
)

IST = opd_helpers.IST


def receptionist_appointment_status_from_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"scheduled", "completed", "cancelled"}:
        return normalized
    raise HTTPException(
        status_code=422,
        detail="Invalid status filter. Use 'scheduled', 'completed', or 'cancelled'.",
    )


def _receptionist_display_status(appointment: Appointment) -> str:
    return status_value(appointment.status)


def _apply_receptionist_status_filter(query, status: str | None):
    # Hide system no_show from receptionist frontend boards.
    query = query.filter(Appointment.status != AppointmentStatus.no_show)
    if status is None:
        return query
    if status == "completed":
        return query.filter(Appointment.status == AppointmentStatus.completed)
    if status == "cancelled":
        return query.filter(Appointment.status == AppointmentStatus.cancelled)
    if status == "scheduled":
        return query.filter(Appointment.status == AppointmentStatus.scheduled)
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
        "scheduled_at": appointment.scheduled_at,
        "checked_in_at": queue.queue_entered_at if queue else None,
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


def _latest_queue_subquery(db: Session):
    """One queue row per appointment+date (highest id)."""
    return (
        db.query(
            PatientQueue.appointment_id.label("appointment_id"),
            PatientQueue.queue_date.label("queue_date"),
            func.max(PatientQueue.id).label("queue_id"),
        )
        .group_by(PatientQueue.appointment_id, PatientQueue.queue_date)
        .subquery()
    )


def _receptionist_appointments_query(
    db: Session,
    *,
    date_from: date,
    date_to: date | None = None,
    doctor_id: Optional[int] = None,
    payment_filter: Optional[str] = None,
):
    """Appointments in range with latest visit and single queue row for that day."""
    date_to = date_to or date_from
    range_start = datetime.combine(date_from, time.min, tzinfo=IST)
    range_end = datetime.combine(date_to, time.max, tzinfo=IST)
    latest_visit = _latest_visit_subquery(db)
    latest_queue = _latest_queue_subquery(db)
    Visit = aliased(OpdVisit)
    Queue = aliased(PatientQueue)

    q = (
        db.query(Appointment, Patient, Visit, Queue, User)
        .join(Patient, Appointment.patient_id == Patient.id)
        .outerjoin(latest_visit, latest_visit.c.appointment_id == Appointment.id)
        .outerjoin(Visit, Visit.id == latest_visit.c.visit_id)
        .outerjoin(
            latest_queue,
            and_(
                latest_queue.c.appointment_id == Appointment.id,
                latest_queue.c.queue_date
                == func.date(func.timezone("Asia/Kolkata", Appointment.scheduled_at)),
            ),
        )
        .outerjoin(Queue, Queue.id == latest_queue.c.queue_id)
        .outerjoin(User, Appointment.doctor_id == User.id)
        .filter(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at <= range_end,
            Appointment.status != AppointmentStatus.cancelled,
            Appointment.status != AppointmentStatus.no_show,
        )
    )
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    q = apply_receptionist_payment_filter(q, payment_filter, visit_model=Visit)
    return q, Visit


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


def _canonical_priority_order(Visit):
    """
    Canonical pick when collapsing duplicates:
    1. Paid appointment
    2. Linked visit
    3. Latest scheduled_at
    4. Highest appointment id
    """
    is_paid = case(
        (and_(Visit.id.isnot(None), is_visit_paid_sql(Visit)), 1),
        else_=0,
    )
    has_visit = case((Visit.id.isnot(None), 1), else_=0)
    return (
        is_paid.desc(),
        has_visit.desc(),
        Appointment.scheduled_at.desc(),
        Appointment.id.desc(),
    )


def _count_distinct_appointments(query) -> int:
    return (
        query.order_by(None)
        .with_entities(Appointment.id)
        .distinct()
        .count()
    )


def _canonical_rows(query, Visit, *, partition_by_patient: bool = True):
    """
    One appointment → one queue row.
    Same-day boards also collapse to one canonical appointment per patient:
    paid > linked visit > latest scheduled_at > highest id.
    """
    if partition_by_patient:
        return (
            query.order_by(
                Appointment.patient_id.asc(),
                *_canonical_priority_order(Visit),
            )
            .distinct(Appointment.patient_id)
            .all()
        )
    return (
        query.order_by(
            Appointment.id.asc(),
            *_canonical_priority_order(Visit),
        )
        .distinct(Appointment.id)
        .all()
    )


def _paginate_rows(rows: list, page: int, limit: int, *, sort_key, reverse: bool = False):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    ordered = sorted(rows, key=sort_key, reverse=reverse)
    total = len(ordered)
    start = (page - 1) * limit
    return ordered[start : start + limit], total, page, limit


def _today_range() -> tuple[datetime, datetime]:
    start = opd_helpers.today_start_ist()
    return start, start + timedelta(days=1)


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
    from Services.doctor_appointment_service import mark_past_scheduled_as_no_show

    mark_past_scheduled_as_no_show(db)
    all_q, _ = _todays_appointments_query(db, doctor_id=doctor_id)
    paid_q, _ = _todays_appointments_query(db, doctor_id=doctor_id, payment_filter="paid")
    unpaid_q, _ = _todays_appointments_query(
        db, doctor_id=doctor_id, payment_filter="unpaid"
    )
    completed_q, _ = _todays_appointments_query(db, doctor_id=doctor_id)
    completed_q = _apply_receptionist_status_filter(completed_q, "completed")

    return {
        "total_patients": _count_distinct_appointments(all_q),
        "completed": _count_distinct_appointments(completed_q),
        "todays_paid_appointments": _count_distinct_appointments(paid_q),
        "todays_unpaid_appointments": _count_distinct_appointments(unpaid_q),
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
    from Services.doctor_appointment_service import mark_past_scheduled_as_no_show

    mark_past_scheduled_as_no_show(db)
    today = _today()
    q, Visit = _todays_appointments_query(
        db, doctor_id=doctor_id, payment_filter=payment_filter
    )
    if doctor_name:
        q = q.filter(_doctor_name_filter(doctor_name))
    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))

    canonical = _canonical_rows(q, Visit)
    rows, total, page, limit = _paginate_rows(
        canonical,
        page,
        limit,
        sort_key=lambda r: (r[0].scheduled_at, r[0].id),
    )
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
                doctor_name=opd_helpers.display_name(
                    doc.first_name, doc.last_name, prefix="Dr. "
                )
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
    q, Visit = _receptionist_appointments_query(
        db,
        date_from=target_date,
        date_to=target_date,
        doctor_id=doctor_id,
        payment_filter=payment_filter,
    )
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search))

    canonical = _canonical_rows(q, Visit)
    if page is not None and limit is not None:
        rows, total, page, limit = _paginate_rows(
            canonical,
            page,
            limit,
            sort_key=lambda r: (r[0].scheduled_at, r[0].id),
        )
    else:
        rows = sorted(canonical, key=lambda r: (r[0].scheduled_at, r[0].id))
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

    q, Visit = _receptionist_appointments_query(
        db,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        payment_filter=payment_filter,
    )
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))
    return q, Visit, date_from, date_to


def _unique_appointment_rows(query, Visit):
    """History: one row per appointment across the date range."""
    return _canonical_rows(query, Visit, partition_by_patient=False)


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
    q, Visit, date_from, date_to = _queue_history_query(
        db,
        single_date=single_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        status=status,
        payment_filter=payment_filter,
        search=search,
    )

    unique_rows = _unique_appointment_rows(q, Visit)
    rows, total, page, limit = _paginate_rows(
        unique_rows,
        page,
        limit,
        sort_key=lambda r: (r[0].scheduled_at, r[0].id),
        reverse=True,
    )
    history = [
        _appointment_row_to_dict(
            appointment,
            patient,
            visit,
            queue,
            doctor_name=opd_helpers.display_name(
                doc.first_name, doc.last_name, prefix="Dr. "
            )
            if doc
            else None,
            queue_date=(
                queue.queue_date
                if queue
                else appointment.scheduled_at.astimezone(IST).date()
            ),
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


def _appointment_counts_by_doctor(db: Session, target_date: date) -> dict[int, dict]:
    """Per-doctor appointment totals for the given IST calendar date."""
    range_start = datetime.combine(target_date, time.min, tzinfo=IST)
    range_end = datetime.combine(target_date, time.max, tzinfo=IST)
    rows = (
        db.query(
            Appointment.doctor_id,
            func.count(Appointment.id).label("appointments_count"),
            func.sum(
                case(
                    (Appointment.status == AppointmentStatus.scheduled, 1),
                    else_=0,
                )
            ).label("scheduled_count"),
            func.sum(
                case(
                    (Appointment.status == AppointmentStatus.completed, 1),
                    else_=0,
                )
            ).label("completed_count"),
            func.sum(
                case(
                    (Appointment.status == AppointmentStatus.cancelled, 1),
                    else_=0,
                )
            ).label("cancelled_count"),
        )
        .filter(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at <= range_end,
        )
        .group_by(Appointment.doctor_id)
        .all()
    )
    return {
        row.doctor_id: {
            "appointments_count": int(row.appointments_count or 0),
            "scheduled_count": int(row.scheduled_count or 0),
            "completed_count": int(row.completed_count or 0),
            "cancelled_count": int(row.cancelled_count or 0),
        }
        for row in rows
    }


def get_doctors_schedule(
    db: Session,
    *,
    schedule_date: date,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    View-only doctor board for a date (IST).

    Returns active doctors with shift fields from doctor_profiles and that day's
    appointment counts. Filters: doctor_id, department_id, search, page, page_size.
    """
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    search_term = search.strip() if search and search.strip() else None

    q = (
        db.query(User)
        .options(joinedload(User.doctor_profile), joinedload(User.department))
        .join(Role, User.role_id == Role.id)
        .outerjoin(Department, User.department_id == Department.id)
        .filter(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.name == opd_helpers.DOCTOR_ROLE,
        )
    )
    if doctor_id is not None:
        q = q.filter(User.id == doctor_id)
    if department_id is not None:
        q = q.filter(User.department_id == department_id)
    if search_term:
        pattern = f"%{search_term}%"
        q = q.filter(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.specialization.ilike(pattern),
                Department.name.ilike(pattern),
                cast(User.id, String).ilike(pattern),
                func.concat(User.first_name, " ", func.coalesce(User.last_name, "")).ilike(
                    pattern
                ),
            )
        )

    total = (
        q.order_by(None)
        .with_entities(User.id)
        .distinct()
        .count()
    )
    doctors = (
        q.order_by(User.first_name.asc(), User.last_name.asc(), User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    counts = _appointment_counts_by_doctor(db, schedule_date)
    empty_stats = {
        "appointments_count": 0,
        "scheduled_count": 0,
        "completed_count": 0,
        "cancelled_count": 0,
    }

    items = []
    for doctor in doctors:
        profile: DoctorProfile | None = doctor.doctor_profile
        dept: Department | None = doctor.department
        stats = counts.get(doctor.id, empty_stats)
        items.append(
            {
                "doctor_id": doctor.id,
                "doctor_name": opd_helpers.display_name(
                    doctor.first_name, doctor.last_name, prefix="Dr. "
                ),
                "department_id": doctor.department_id,
                "department_name": dept.name if dept else None,
                "specialization": doctor.specialization,
                "shift_name": profile.shift_name if profile else None,
                "shift_start_time": profile.shift_start_time if profile else None,
                "shift_end_time": profile.shift_end_time if profile else None,
                "appointments_count": stats["appointments_count"],
                "scheduled_count": stats["scheduled_count"],
                "completed_count": stats["completed_count"],
                "cancelled_count": stats["cancelled_count"],
                # Active doctors are listable; shift fields indicate configured hours.
                "is_available": True,
            }
        )

    return {
        "date": schedule_date,
        "total": total,
        "page": page,
        "page_size": page_size,
        "doctors": items,
    }
