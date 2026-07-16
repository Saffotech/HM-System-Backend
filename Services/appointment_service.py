"""OPD appointment booking."""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, and_, case, cast, exists, func, or_
from sqlalchemy.orm import Session, aliased

from Models.department import Department
from Models.opd_billing import Appointment, AppointmentStatus
from Models.patient import OpdVisit, Patient
from Models.user import User
from Schemas.opd_schema import AppointmentCreate, AppointmentOut, AppointmentUpdate
from Services import opd_helpers as h
from Services.queue_helpers import appointment_status_value

LIST_FILTERS = frozenset({"all", "scheduled", "pending", "completed", "cancelled"})
LIST_SORT_FIELDS = frozenset({"scheduled_at"})
SORT_ORDERS = frozenset({"asc", "desc"})
_OPD_LIST_STATUSES = (
    AppointmentStatus.scheduled,
    AppointmentStatus.completed,
    AppointmentStatus.cancelled,
)
# Active slots that may be reused for the same patient+doctor+dept+day.
_ACTIVE_REUSE_STATUSES = (
    AppointmentStatus.scheduled,
    AppointmentStatus.waiting,
    AppointmentStatus.in_progress,
)


def _payment_from_visit(visit: OpdVisit | None) -> dict:
    if visit is None:
        return {
            "payment_status": "no_bill",
            "bill_id": None,
            "bill_number": None,
            "total_amount": 0.0,
            "paid_amount": 0.0,
            "balance_amount": 0.0,
        }

    paid = float(visit.paid_amount or 0)
    total = float(visit.grand_total or 0)
    balance = float(
        visit.balance_due
        if visit.balance_due is not None
        else max(total - paid, 0)
    )

    return {
        "payment_status": visit.payment_status,
        "bill_id": visit.id,
        "bill_number": visit.bill_number,
        "total_amount": total,
        "paid_amount": paid,
        "balance_amount": balance,
    }


def _to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=h.IST)
    return dt.astimezone(h.IST)


def _day_window(scheduled_at: datetime) -> tuple[datetime, datetime]:
    day = _to_ist(scheduled_at).date()
    start = datetime.combine(day, time.min, tzinfo=h.IST)
    end = start + timedelta(days=1)
    return start, end


def iso_scheduled_at(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return _to_ist(dt).isoformat()


def find_active_appointment_same_day(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    department_id: int,
    scheduled_at: datetime,
) -> Optional[Appointment]:
    """Return the newest active appointment for patient+doctor+dept on that IST day."""
    start, end = _day_window(scheduled_at)
    return (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.department_id == department_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
            Appointment.status.in_(_ACTIVE_REUSE_STATUSES),
        )
        .order_by(Appointment.id.desc())
        .first()
    )


def resolve_appointment_for_visit(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    department_id: int,
    created_by: int,
    scheduled_at: Optional[datetime] = None,
    appointment_id: Optional[int] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    appointment_type: str = "opd",
) -> Appointment:
    """
    Single source of truth for registration/revisit appointment linking.

    Reuses an active appointment for the same patient + doctor + department + day.
    Creates one new row only when none exists. Never auto-creates a second slot.
    """
    h.get_patient(db, patient_id)
    h.get_department(db, department_id)
    h.get_doctor_in_department(db, doctor_id, department_id)

    slot = _to_ist(scheduled_at) if scheduled_at is not None else h.now_ist()

    if appointment_id is not None:
        apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not apt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if apt.patient_id != patient_id:
            raise HTTPException(
                status_code=400,
                detail="Appointment does not belong to this patient",
            )
        if apt.status == AppointmentStatus.cancelled:
            raise HTTPException(
                status_code=400,
                detail="Cannot bill a cancelled appointment",
            )
        if scheduled_at is not None and apt.status != AppointmentStatus.completed:
            apt.scheduled_at = slot
        if reason and not apt.reason:
            apt.reason = reason
        if notes and not apt.notes:
            apt.notes = notes
        db.flush()
        return apt

    existing = find_active_appointment_same_day(
        db,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        scheduled_at=slot,
    )
    if existing is not None:
        if scheduled_at is not None and existing.status != AppointmentStatus.completed:
            existing.scheduled_at = slot
        if reason and not existing.reason:
            existing.reason = reason
        if notes and not existing.notes:
            existing.notes = notes
        db.flush()
        return existing

    apt = Appointment(
        appointment_uid=h.next_appointment_uid(db),
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        scheduled_at=slot,
        reason=reason,
        notes=notes,
        appointment_type=appointment_type,
        status=AppointmentStatus.scheduled,
        created_by=created_by,
    )
    db.add(apt)
    db.flush()
    return apt


def _load_visits_for_appointments(
    db: Session, appointments: list[Appointment]
) -> dict[int, OpdVisit]:
    """Prefer OpdVisit.appointment_id FK; fall back to legacy day matching."""
    if not appointments:
        return {}

    matched: dict[int, OpdVisit] = {}
    apt_ids = [a.id for a in appointments]

    linked = (
        db.query(OpdVisit)
        .filter(
            OpdVisit.appointment_id.in_(apt_ids),
            OpdVisit.status != "cancelled",
        )
        .order_by(OpdVisit.id.desc())
        .all()
    )
    for visit in linked:
        if visit.appointment_id is not None and visit.appointment_id not in matched:
            matched[visit.appointment_id] = visit

    remaining = [a for a in appointments if a.id not in matched]
    if not remaining:
        return matched

    patient_ids = {a.patient_id for a in remaining}
    scheduled_times = [a.scheduled_at for a in remaining if a.scheduled_at]
    if not scheduled_times:
        return matched

    range_start = min(_to_ist(t) for t in scheduled_times).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    range_end = max(_to_ist(t) for t in scheduled_times).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )

    visits = (
        db.query(OpdVisit)
        .filter(
            OpdVisit.patient_id.in_(patient_ids),
            OpdVisit.visit_date >= range_start,
            OpdVisit.visit_date <= range_end,
            OpdVisit.status != "cancelled",
        )
        .all()
    )

    for apt in remaining:
        if not apt.scheduled_at:
            continue
        apt_day = _to_ist(apt.scheduled_at).date()
        best: OpdVisit | None = None

        for visit in visits:
            # Prefer exact FK already handled; skip visits linked to another apt
            if visit.appointment_id is not None and visit.appointment_id != apt.id:
                continue
            if (
                visit.patient_id == apt.patient_id
                and visit.doctor_id == apt.doctor_id
                and visit.department_id == apt.department_id
                and visit.visit_date
                and _to_ist(visit.visit_date).date() == apt_day
            ):
                if best is None or visit.visit_date > best.visit_date:
                    best = visit

        if best is not None:
            matched[apt.id] = best

    return matched


def _visit_for_appointment(db: Session, apt: Appointment) -> OpdVisit | None:
    return _load_visits_for_appointments(db, [apt]).get(apt.id)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=h.IST)
    end = datetime.combine(day, time.max, tzinfo=h.IST)
    return start, end


def _resolve_status_filter(status: Optional[str]) -> Optional[AppointmentStatus]:
    if not status:
        return None
    try:
        return AppointmentStatus(status)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in AppointmentStatus)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Use one of: {allowed}",
        ) from exc


def _resolve_list_filter(list_filter: Optional[str]) -> Optional[str]:
    if not list_filter:
        return None
    value = list_filter.strip().lower()
    if value not in LIST_FILTERS:
        allowed = ", ".join(sorted(LIST_FILTERS))
        raise HTTPException(
            status_code=422,
            detail=f"Invalid list_filter '{list_filter}'. Use one of: {allowed}",
        )
    return value


def _resolve_sort_order(
    sort: Optional[str] = None,
    order: Optional[str] = None,
) -> tuple[str, str]:
    sort_key = (sort or "scheduled_at").strip().lower()
    if sort_key not in LIST_SORT_FIELDS:
        allowed = ", ".join(sorted(LIST_SORT_FIELDS))
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort '{sort}'. Use one of: {allowed}",
        )
    order_key = (order or "desc").strip().lower()
    if order_key not in SORT_ORDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid order '{order}'. Use one of: asc, desc",
        )
    return sort_key, order_key


def _apply_sort(q, sort_key: str, order_key: str):
    col = Appointment.scheduled_at
    if order_key == "desc":
        return q.order_by(col.desc())
    return q.order_by(col.asc())


def _search_filter_clauses(term: str):
    pattern = f"%{term.strip()}%"
    clauses = [
        Patient.first_name.ilike(pattern),
        Patient.last_name.ilike(pattern),
        Patient.patient_uid.ilike(pattern),
        Patient.phone.ilike(pattern),
        Appointment.appointment_uid.ilike(pattern),
        User.first_name.ilike(pattern),
        User.last_name.ilike(pattern),
    ]
    if term.strip().isdigit():
        clauses.append(cast(Appointment.patient_id, String).ilike(pattern))
    return clauses


def _appointment_notes_reason_lower():
    return func.lower(
        func.concat(
            func.coalesce(Appointment.notes, ""),
            " ",
            func.coalesce(Appointment.reason, ""),
        )
    )


def _is_registration_booking_expr():
    text = _appointment_notes_reason_lower()
    return and_(
        ~text.contains("[pay-later]"),
        or_(
            text.contains("booked during registration"),
            text.contains("new patient registration"),
        ),
    )


def _is_pay_later_expr():
    return _appointment_notes_reason_lower().contains("[pay-later]")


def _visit_balance_expr(visit_col):
    owed = visit_col.grand_total - func.coalesce(visit_col.paid_amount, 0)
    return case(
        (visit_col.balance_due.isnot(None), visit_col.balance_due),
        (owed > 0, owed),
        else_=0,
    )


def _visit_unpaid_expr(visit_col):
    balance = _visit_balance_expr(visit_col)
    return and_(
        visit_col.id.isnot(None),
        visit_col.payment_status != "paid",
        or_(
            visit_col.payment_status.in_(("pending", "partial", "unpaid")),
            balance > 0.01,
        ),
    )


def _patient_open_bill_exists():
    open_visit = aliased(OpdVisit)
    return exists().where(
        and_(
            open_visit.patient_id == Appointment.patient_id,
            open_visit.status != "cancelled",
            open_visit.payment_status != "paid",
            or_(
                open_visit.payment_status.in_(("pending", "partial", "unpaid")),
                _visit_balance_expr(open_visit) > 0.01,
            ),
        )
    )


def _matching_visit_id_subquery(db: Session):
    return (
        db.query(OpdVisit.id)
        .filter(
            OpdVisit.patient_id == Appointment.patient_id,
            OpdVisit.doctor_id == Appointment.doctor_id,
            OpdVisit.department_id == Appointment.department_id,
            func.date(OpdVisit.visit_date) == func.date(Appointment.scheduled_at),
            OpdVisit.status != "cancelled",
        )
        .order_by(OpdVisit.visit_date.desc())
        .correlate(Appointment)
        .limit(1)
        .scalar_subquery()
    )


def _scheduled_unpaid_expr(visit_col):
    """Matches frontend Pending: scheduled + unpaid payment state."""
    return and_(
        Appointment.status == AppointmentStatus.scheduled,
        ~_is_registration_booking_expr(),
        or_(
            _visit_unpaid_expr(visit_col),
            and_(_is_pay_later_expr(), _patient_open_bill_exists()),
        ),
    )


def _join_matching_visit(q, db: Session):
    visit_col = aliased(OpdVisit)
    return q.outerjoin(visit_col, visit_col.id == _matching_visit_id_subquery(db)), visit_col


def _apply_list_filter(q, db: Session, list_filter: Optional[str]):
    if not list_filter:
        return q

    q = q.filter(Appointment.status.in_(_OPD_LIST_STATUSES))

    if list_filter == "completed":
        return q.filter(Appointment.status == AppointmentStatus.completed)
    if list_filter == "cancelled":
        return q.filter(Appointment.status == AppointmentStatus.cancelled)
    if list_filter == "all":
        return q.filter(Appointment.status == AppointmentStatus.scheduled)

    q, visit_col = _join_matching_visit(q, db)
    if list_filter == "pending":
        return q.filter(_scheduled_unpaid_expr(visit_col))
    if list_filter == "scheduled":
        return q.filter(~_scheduled_unpaid_expr(visit_col)).filter(
            Appointment.status == AppointmentStatus.scheduled
        )
    return q


def _compute_list_counts(db: Session, q) -> dict[str, int]:
    """UI pill counts for the OPD appointments page (same rules as list_filter)."""
    visible = q.filter(Appointment.status.in_(_OPD_LIST_STATUSES))
    joined, visit_col = _join_matching_visit(visible, db)

    return {
        "all": visible.filter(Appointment.status == AppointmentStatus.scheduled).count(),
        "scheduled": joined.filter(
            Appointment.status == AppointmentStatus.scheduled,
            ~_scheduled_unpaid_expr(visit_col),
        ).count(),
        "pending": joined.filter(_scheduled_unpaid_expr(visit_col)).count(),
        "completed": visible.filter(
            Appointment.status == AppointmentStatus.completed
        ).count(),
        "cancelled": visible.filter(
            Appointment.status == AppointmentStatus.cancelled
        ).count(),
    }


def _apply_appointment_filters(
    db: Session,
    *,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    appointment_date: Optional[date] = None,
    date_from=None,
    date_to=None,
):
    q = db.query(Appointment)

    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if department_id is not None:
        q = q.filter(Appointment.department_id == department_id)

    status_enum = _resolve_status_filter(status)
    if status_enum is not None:
        q = q.filter(Appointment.status == status_enum)

    if appointment_date is not None:
        day_start, day_end = _day_bounds(appointment_date)
        q = q.filter(
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at <= day_end,
        )
    else:
        if date_from is not None:
            q = q.filter(Appointment.scheduled_at >= date_from)
        if date_to is not None:
            q = q.filter(Appointment.scheduled_at <= date_to)

    if search and search.strip():
        q = (
            q.outerjoin(Patient, Patient.id == Appointment.patient_id)
            .outerjoin(User, User.id == Appointment.doctor_id)
            .filter(or_(*_search_filter_clauses(search)))
            .distinct()
        )

    return q


def _load_related_maps(
    db: Session, appointments: list[Appointment]
) -> tuple[dict[int, Patient], dict[int, User], dict[int, Department]]:
    if not appointments:
        return {}, {}, {}

    patient_ids = {a.patient_id for a in appointments if a.patient_id}
    doctor_ids = {a.doctor_id for a in appointments if a.doctor_id}
    dept_ids = {a.department_id for a in appointments if a.department_id}

    patients = {
        p.id: p for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    }
    doctors = {
        u.id: u for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    }
    departments = {
        d.id: d for d in db.query(Department).filter(Department.id.in_(dept_ids)).all()
    }
    return patients, doctors, departments


def _appointment_out(
    db: Session,
    apt: Appointment,
    visit: OpdVisit | None = None,
    *,
    patients: dict[int, Patient] | None = None,
    doctors: dict[int, User] | None = None,
    departments: dict[int, Department] | None = None,
) -> AppointmentOut:
    if patients is None:
        patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
        doctor = db.query(User).filter(User.id == apt.doctor_id).first()
        dept = db.query(Department).filter(Department.id == apt.department_id).first()
    else:
        patient = patients.get(apt.patient_id)
        doctor = doctors.get(apt.doctor_id) if doctors else None
        dept = departments.get(apt.department_id) if departments else None
    payment = _payment_from_visit(visit)

    return AppointmentOut(
        id=apt.id,
        appointment_uid=apt.appointment_uid,
        patient_id=apt.patient_id,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else "",
        patient_uid=patient.patient_uid if patient else "",
        doctor_id=apt.doctor_id,
        doctor_name=h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. ") if doctor else "",
        department_id=apt.department_id,
        department_name=dept.name if dept else "",
        scheduled_at=apt.scheduled_at.isoformat() if apt.scheduled_at else "",
        reason=apt.reason,
        notes=apt.notes,
        appointment_type=apt.appointment_type,
        status=appointment_status_value(apt.status),
        **payment,
    )


def _appointments_out_list(
    db: Session,
    rows: list[Appointment],
    visit_map: dict[int, OpdVisit],
) -> list[AppointmentOut]:
    patients, doctors, departments = _load_related_maps(db, rows)
    return [
        _appointment_out(
            db,
            apt,
            visit_map.get(apt.id),
            patients=patients,
            doctors=doctors,
            departments=departments,
        )
        for apt in rows
    ]


def create_appointment(db: Session, data: AppointmentCreate, created_by: int) -> AppointmentOut:
    """Create or reuse one active appointment for the patient+doctor+dept+day."""
    apt = resolve_appointment_for_visit(
        db,
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        department_id=data.department_id,
        created_by=created_by,
        scheduled_at=data.scheduled_at,
        reason=data.reason,
        notes=data.notes,
        appointment_type=data.appointment_type,
    )
    db.commit()
    db.refresh(apt)
    return _appointment_out(db, apt, _visit_for_appointment(db, apt))


def create_walk_in_appointment(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    department_id: int,
    created_by: int,
    reason: str = "OPD walk-in",
) -> Appointment:
    """Resolve today's appointment for walk-in check-in — never create a day duplicate."""
    return resolve_appointment_for_visit(
        db,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        created_by=created_by,
        scheduled_at=h.now_ist(),
        reason=reason,
        appointment_type="opd",
    )


def list_appointments(
    db: Session,
    *,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    list_filter: Optional[str] = None,
    search: Optional[str] = None,
    appointment_date: Optional[date] = None,
    date_from=None,
    date_to=None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    resolved_list_filter = _resolve_list_filter(list_filter)
    sort_key, order_key = _resolve_sort_order(sort, order)
    effective_status = None if resolved_list_filter else status

    filters_q = _apply_appointment_filters(
        db,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        status=effective_status,
        search=search,
        appointment_date=appointment_date,
        date_from=date_from,
        date_to=date_to,
    )
    result_q = _apply_sort(
        _apply_list_filter(filters_q, db, resolved_list_filter),
        sort_key,
        order_key,
    )

    total = result_q.count()
    rows = result_q.offset((page - 1) * limit).limit(limit).all()
    visit_map = _load_visits_for_appointments(db, rows)

    counts = {
        status_name: filters_q.filter(Appointment.status == status_name).count()
        for status_name in ("scheduled", "completed", "cancelled")
    }
    list_counts = _compute_list_counts(db, filters_q)

    return {
        "counts": counts,
        "list_counts": list_counts,
        "total": total,
        "page": page,
        "limit": limit,
        "appointments": _appointments_out_list(db, rows, visit_map),
    }


def update_appointment(db: Session, appointment_id: int, data: AppointmentUpdate) -> AppointmentOut:
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    updates = data.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None:
        try:
            updates["status"] = AppointmentStatus(updates["status"])
        except ValueError as exc:
            allowed = ", ".join(s.value for s in AppointmentStatus)
            raise HTTPException(
                status_code=422,
                detail=f"Invalid appointment status. Use one of: {allowed}",
            ) from exc

    if updates.get("scheduled_at") is not None and apt.status == AppointmentStatus.completed:
        apt.status = AppointmentStatus.scheduled

    for key, value in updates.items():
        setattr(apt, key, value)

    db.commit()
    db.refresh(apt)
    return _appointment_out(db, apt, _visit_for_appointment(db, apt))


def cancel_appointment(db: Session, appointment_id: int) -> AppointmentOut:
    return update_appointment(
        db, appointment_id, AppointmentUpdate(status=AppointmentStatus.cancelled.value)
    )


def doctor_availability(db: Session, doctor_id: int, department_id: int, date_str: str) -> dict:
    h.get_doctor_in_department(db, doctor_id, department_id)
    from datetime import datetime

    day = datetime.fromisoformat(date_str).replace(tzinfo=h.IST)
    day_end = day.replace(hour=23, minute=59, second=59)

    booked = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at >= day,
            Appointment.scheduled_at <= day_end,
            Appointment.status == "scheduled",
        )
        .all()
    )
    slots = []
    for hour in range(9, 17):
        for minute in (0, 30):
            slot_time = day.replace(hour=hour, minute=minute)
            taken = any(a.scheduled_at == slot_time for a in booked)
            slots.append({
                "time": slot_time.strftime("%H:%M"),
                "status": "booked" if taken else "available",
            })

    return {"doctor_id": doctor_id, "date": date_str, "slots": slots}
