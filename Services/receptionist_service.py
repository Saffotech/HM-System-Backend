"""Receptionist module — view-only appointment boards (scheduled / completed)."""
from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session, aliased

from Models.department import Department
from Models.doctor_availability import DoctorLeave, DoctorSchedule, LeaveType
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


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _format_hhmm(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _calculate_total_slots(shift_start: time, shift_end: time, duration_minutes: int) -> int:
    window = _time_to_minutes(shift_end) - _time_to_minutes(shift_start)
    if window <= 0 or duration_minutes <= 0:
        return 0
    return window // duration_minutes


def _resolve_schedule_status(
    *,
    on_leave: bool,
    on_holiday: bool,
    has_schedule: bool,
    total_slots: int,
    available_slots: int,
) -> str:
    if on_holiday:
        return "Holiday"
    if on_leave:
        return "On Leave"
    if not has_schedule:
        return "No Schedule"
    if total_slots > 0 and available_slots <= 0:
        return "Fully Booked"
    return "Available"


def get_doctor_schedules(
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
    View-only doctor schedule and availability for reception.
    Slots are calculated dynamically from schedule minus booked appointments.
    """
    weekday = schedule_date.weekday()

    doctors_q = (
        db.query(User, Department, DoctorSchedule)
        .join(Role, User.role_id == Role.id)
        .outerjoin(Department, User.department_id == Department.id)
        .outerjoin(
            DoctorSchedule,
            and_(
                DoctorSchedule.doctor_id == User.id,
                DoctorSchedule.day_of_week == weekday,
                DoctorSchedule.is_active.is_(True),
            ),
        )
        .filter(
            Role.name == "doctor",
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )

    if doctor_id is not None:
        doctors_q = doctors_q.filter(User.id == doctor_id)
    if department_id is not None:
        doctors_q = doctors_q.filter(User.department_id == department_id)
    if search:
        term = f"%{search.strip()}%"
        doctors_q = doctors_q.filter(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                Department.name.ilike(term),
                User.specialization.ilike(term),
            )
        )

    doctors_q = doctors_q.order_by(
        Department.name.asc().nulls_last(),
        User.first_name.asc(),
        User.last_name.asc(),
        DoctorSchedule.shift_start.asc().nulls_last(),
    )

    total_records = doctors_q.count()
    if doctor_id is not None and total_records == 0:
        raise HTTPException(status_code=404, detail="Doctor not found")

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    total_pages = ceil(total_records / page_size) if total_records else 0
    rows = doctors_q.offset((page - 1) * page_size).limit(page_size).all()

    if not rows:
        return {
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "items": [],
        }

    doctor_ids = [user.id for user, _, _ in rows]

    leave_rows = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id.in_(doctor_ids),
            DoctorLeave.is_active.is_(True),
            DoctorLeave.start_date <= schedule_date,
            DoctorLeave.end_date >= schedule_date,
        )
        .all()
    )
    leave_map: dict[int, set[str]] = {did: set() for did in doctor_ids}
    for leave in leave_rows:
        leave_map.setdefault(leave.doctor_id, set()).add(leave.leave_type.value)

    booked_rows = (
        db.query(Appointment.doctor_id, func.count(Appointment.id))
        .filter(
            dh.scheduled_on_date(schedule_date),
            Appointment.doctor_id.in_(doctor_ids),
            Appointment.status != AppointmentStatus.cancelled,
        )
        .group_by(Appointment.doctor_id)
        .all()
    )
    booked_map = {doctor_id: count for doctor_id, count in booked_rows}

    items = []
    for user, dept, schedule in rows:
        on_holiday = LeaveType.holiday.value in leave_map.get(user.id, set())
        on_leave = LeaveType.leave.value in leave_map.get(user.id, set())
        booked_slots = int(booked_map.get(user.id, 0))

        if schedule:
            duration = schedule.consultation_duration_minutes or 15
            total_slots = _calculate_total_slots(
                schedule.shift_start, schedule.shift_end, duration
            )
            shift_start = _format_hhmm(schedule.shift_start)
            shift_end = _format_hhmm(schedule.shift_end)
        else:
            duration = 15
            total_slots = 0
            shift_start = None
            shift_end = None

        available_slots = max(total_slots - booked_slots, 0)
        status = _resolve_schedule_status(
            on_leave=on_leave,
            on_holiday=on_holiday,
            has_schedule=schedule is not None,
            total_slots=total_slots,
            available_slots=available_slots,
        )

        items.append(
            {
                "doctor_id": user.id,
                "doctor_name": opd_helpers.display_name(
                    user.first_name, user.last_name, prefix="Dr. "
                ),
                "department": dept.name if dept else None,
                "specialization": user.specialization,
                "schedule_date": schedule_date,
                "shift_start": shift_start,
                "shift_end": shift_end,
                "total_slots": total_slots,
                "booked_slots": booked_slots,
                "available_slots": available_slots,
                "status": status,
            }
        )

    return {
        "total_records": total_records,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "items": items,
    }
