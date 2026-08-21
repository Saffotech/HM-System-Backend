"""Receptionist module — view-only appointment boards (scheduled / completed).

Hot paths (dashboard / today-queue / doctor-queue / history / schedule) are
optimized for SQL-first counts, DISTINCT ON canonical rows, cheap ID pagination,
throttled day-rollover, and batched schedule slots.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from time import monotonic
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
from Services import opd_settings_service as opd_settings_svc
from Services.queue_helpers import (
    apply_receptionist_payment_filter,
    is_visit_paid,
    is_visit_paid_sql,
    status_value,
)

IST = opd_helpers.IST

# Throttle expensive past-appointment rollover on hot receptionist GETs.
_LIFECYCLE_TTL_SEC = 60.0
_last_lifecycle_at: float = 0.0


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
    """Latest linked visit payment — same rules as OPD/billing (is_visit_paid)."""
    if visit is None:
        return "pending"
    if is_visit_paid(visit):
        return "paid"
    raw = (visit.payment_status or "pending").strip().lower()
    if raw in {"paid", "partial", "pending"}:
        return raw
    return "pending"


def _appointment_row_to_dict(
    appointment: Appointment,
    patient: Patient,
    visit: OpdVisit | None,
    queue: PatientQueue | None,
    *,
    doctor_name: str | None = None,
    department_id: int | None = None,
    department: str | None = None,
    queue_date: date | None = None,
) -> dict:
    resolved_department_id = (
        department_id
        if department_id is not None
        else getattr(appointment, "department_id", None)
    )
    data = {
        "appointment_id": appointment.id,
        "appointment_uid": appointment.appointment_uid,
        "patient_id": patient.id,
        "patient_name": opd_helpers.display_name(patient.first_name, patient.last_name),
        "patient_uid": patient.patient_uid,
        "patient_phone": patient.phone,
        "doctor_id": appointment.doctor_id,
        "department_id": resolved_department_id,
        "department": department,
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


def _to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _canonical_group_key(appointment: Appointment) -> tuple:
    day = _to_ist(appointment.scheduled_at).date() if appointment.scheduled_at else None
    return (appointment.patient_id, appointment.doctor_id, day)


def _canonical_rank(appointment: Appointment, visit: OpdVisit | None) -> tuple:
    """Higher rank wins for REC-2 duplicate collapse."""
    paid = 1 if visit is not None and is_visit_paid(visit) else 0
    linked = 1 if visit is not None else 0
    ts = _to_ist(appointment.scheduled_at).timestamp() if appointment.scheduled_at else 0.0
    return (paid, linked, ts, appointment.id)


def _pick_canonical_row(rows: list[tuple]) -> tuple:
    return max(rows, key=lambda row: _canonical_rank(row[0], row[2]))


def _dedupe_canonical_rows(rows: list[tuple]) -> list[tuple]:
    """One row per (patient_id, doctor_id, IST day)."""
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for row in rows:
        appointment = row[0]
        groups[_canonical_group_key(appointment)].append(row)

    canonical: list[tuple] = []
    for group in groups.values():
        by_apt: dict[int, tuple] = {}
        for row in group:
            apt_id = row[0].id
            existing = by_apt.get(apt_id)
            if existing is None:
                by_apt[apt_id] = row
                continue
            # Prefer the row whose queue_date matches the appointment's IST day
            apt_day = (
                _to_ist(row[0].scheduled_at).date() if row[0].scheduled_at else None
            )
            existing_q = existing[3]
            new_q = row[3]
            if (
                new_q is not None
                and apt_day is not None
                and new_q.queue_date == apt_day
                and (existing_q is None or existing_q.queue_date != apt_day)
            ):
                by_apt[apt_id] = row
                continue
            if row[2] is not None and existing[2] is None:
                by_apt[apt_id] = row
            elif row[3] is not None and existing[3] is None:
                by_apt[apt_id] = row
        unique_rows = list(by_apt.values())
        canonical.append(_pick_canonical_row(unique_rows))
    return canonical


def _maybe_mark_past_appointments(db: Session) -> None:
    """Run day-rollover at most once per TTL window (not on every queue poll)."""
    global _last_lifecycle_at
    now = monotonic()
    if now - _last_lifecycle_at < _LIFECYCLE_TTL_SEC:
        return
    _last_lifecycle_at = now
    try:
        from Services.doctor_appointment_service import mark_past_scheduled_as_no_show

        mark_past_scheduled_as_no_show(db)
    except Exception:
        db.rollback()


def _enrich_rows_with_visits(
    db: Session, rows: list[tuple], *, persist_links: bool = True
) -> list[tuple]:
    """
    Attach visits the same way OPD does (FK first, then patient+doctor+dept+day).

    Only re-resolves rows that already lack a joined visit (orphan bills).
    """
    from Services import appointment_service

    if not rows:
        return rows

    missing = [row[0] for row in rows if row[2] is None]
    visit_map = (
        appointment_service._load_visits_for_appointments(db, missing)
        if missing
        else {}
    )
    linked_any = False
    enriched: list[tuple] = []

    for row in rows:
        apt = row[0]
        visit = row[2] if row[2] is not None else visit_map.get(apt.id)
        if persist_links and visit is not None and visit.appointment_id is None:
            visit.appointment_id = apt.id
            linked_any = True
        enriched.append((row[0], row[1], visit, *row[3:]))

    if linked_any:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return enriched


def _filter_canonical_rows(
    rows: list[tuple],
    *,
    status: str | None = None,
    payment_filter: Optional[str] = None,
) -> list[tuple]:
    out = rows
    if status == "completed":
        out = [r for r in out if status_value(r[0].status) == AppointmentStatus.completed.value]
    elif status == "scheduled":
        out = [r for r in out if status_value(r[0].status) != AppointmentStatus.completed.value]

    if payment_filter == "paid":
        out = [r for r in out if r[2] is not None and is_visit_paid(r[2])]
    elif payment_filter == "unpaid":
        out = [r for r in out if r[2] is None or not is_visit_paid(r[2])]
    return out


def _paginate_list(items: list, page: int, limit: int):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    total = len(items)
    start = (page - 1) * limit
    return items[start : start + limit], total, page, limit


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
    department_id: Optional[int] = None,
    payment_filter: Optional[str] = None,
    include_cancelled: bool = False,
):
    """Appointments in range with latest visit and single queue row for that day."""
    date_to = date_to or date_from
    range_start = datetime.combine(date_from, time.min, tzinfo=IST)
    range_end = datetime.combine(date_to, time.max, tzinfo=IST)
    latest_visit = _latest_visit_subquery(db)
    latest_queue = _latest_queue_subquery(db)
    Visit = aliased(OpdVisit)
    Queue = aliased(PatientQueue)

    status_filters = [Appointment.status != AppointmentStatus.no_show]
    if not include_cancelled:
        status_filters.append(Appointment.status != AppointmentStatus.cancelled)

    q = (
        db.query(Appointment, Patient, Visit, Queue, User, Department)
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
        .outerjoin(Department, Appointment.department_id == Department.id)
        .filter(
            Appointment.scheduled_at >= range_start,
            Appointment.scheduled_at <= range_end,
            *status_filters,
        )
    )
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if department_id is not None:
        q = q.filter(Appointment.department_id == department_id)
    q = apply_receptionist_payment_filter(q, payment_filter, visit_model=Visit)
    return q, Visit


def _todays_appointments_query(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    payment_filter: Optional[str] = None,
    include_cancelled: bool = False,
):
    """Today's IST appointments — shared by dashboard and today-queue."""
    today = _today()
    return _receptionist_appointments_query(
        db,
        date_from=today,
        date_to=today,
        doctor_id=doctor_id,
        department_id=department_id,
        payment_filter=payment_filter,
        include_cancelled=include_cancelled,
    )


def _appointment_list_order():
    return (Appointment.scheduled_at.asc(), Appointment.id.asc())


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


def _canonical_rows_patient_doctor(query, Visit):
    """One row per (patient_id, doctor_id) — dashboard paid/unpaid canonical."""
    return (
        query.order_by(
            Appointment.patient_id.asc(),
            Appointment.doctor_id.asc(),
            *_canonical_priority_order(Visit),
        )
        .distinct(Appointment.patient_id, Appointment.doctor_id)
        .all()
    )


def _paginate_rows(rows: list, page: int, limit: int, *, sort_key, reverse: bool = False):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    ordered = sorted(rows, key=sort_key, reverse=reverse)
    total = len(ordered)
    start = (page - 1) * limit
    return ordered[start : start + limit], total, page, limit


def _page_canonical_board(
    db: Session,
    query,
    Visit,
    *,
    partition: str,
    page: int,
    limit: int,
    payment_filter: Optional[str],
    reverse: bool = False,
) -> tuple[list[tuple], int, int, int]:
    """
    Canonical DISTINCT ON → enrich orphan visits only → payment filter → paginate.

    Loads full ORM rows only for the current page (IDs sorted first).
    """
    page = max(page, 1)
    limit = min(max(limit, 1), 100)

    if partition == "patient":
        id_rows = (
            query.order_by(
                Appointment.patient_id.asc(),
                *_canonical_priority_order(Visit),
            )
            .distinct(Appointment.patient_id)
            .with_entities(Appointment.id, Appointment.scheduled_at)
            .all()
        )
    elif partition == "patient_doctor":
        id_rows = (
            query.order_by(
                Appointment.patient_id.asc(),
                Appointment.doctor_id.asc(),
                *_canonical_priority_order(Visit),
            )
            .distinct(Appointment.patient_id, Appointment.doctor_id)
            .with_entities(Appointment.id, Appointment.scheduled_at)
            .all()
        )
    else:
        id_rows = (
            query.order_by(
                Appointment.id.asc(),
                *_canonical_priority_order(Visit),
            )
            .distinct(Appointment.id)
            .with_entities(Appointment.id, Appointment.scheduled_at)
            .all()
        )

    id_rows = sorted(
        id_rows,
        key=lambda r: (r.scheduled_at or datetime.min.replace(tzinfo=IST), r.id),
        reverse=reverse,
    )
    all_ids = [r.id for r in id_rows]
    if not all_ids:
        return [], 0, page, limit

    # Load light rows for payment filter (visit join already on query).
    light = (
        query.filter(Appointment.id.in_(all_ids))
        .order_by(None)
        .all()
    )
    # Deduplicate ORM join fan-out by appointment id.
    by_id: dict[int, tuple] = {}
    for row in light:
        apt = row[0]
        existing = by_id.get(apt.id)
        if existing is None or (row[2] is not None and existing[2] is None):
            by_id[apt.id] = row
    ordered_light = [by_id[i] for i in all_ids if i in by_id]
    ordered_light = _enrich_rows_with_visits(db, ordered_light)
    ordered_light = _filter_canonical_rows(
        ordered_light, status=None, payment_filter=payment_filter
    )

    total = len(ordered_light)
    start = (page - 1) * limit
    page_rows = ordered_light[start : start + limit]
    return page_rows, total, page, limit


def _today_range() -> tuple[datetime, datetime]:
    start = opd_helpers.today_start_ist()
    return start, start + timedelta(days=1)


def _doctor_name_filter(doctor_name: str):
    pattern = f"%{doctor_name.strip()}%"
    return or_(
        User.first_name.ilike(pattern),
        User.last_name.ilike(pattern),
    )


def _load_canonical_rows(
    db: Session,
    *,
    date_from: date,
    date_to: date | None = None,
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    include_doctor_search: bool = False,
    order_desc: bool = False,
) -> list[tuple]:
    q, Visit = _receptionist_appointments_query(
        db,
        date_from=date_from,
        date_to=date_to or date_from,
        doctor_id=doctor_id,
        payment_filter=None,
        include_cancelled=(status == "cancelled"),
    )
    if doctor_name:
        q = q.filter(_doctor_name_filter(doctor_name))
    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    if search:
        q = q.filter(
            _appointment_search_filter(search, include_doctor=include_doctor_search)
        )

    rows = _canonical_rows_patient_doctor(q, Visit)
    rows = _enrich_rows_with_visits(db, rows)
    filtered = _filter_canonical_rows(
        rows, status=status, payment_filter=payment_filter
    )
    reverse = order_desc
    filtered.sort(
        key=lambda r: (
            _to_ist(r[0].scheduled_at) if r[0].scheduled_at else datetime.min.replace(tzinfo=IST),
            r[0].id,
        ),
        reverse=reverse,
    )
    return filtered


def get_dashboard(db: Session, *, doctor_id: Optional[int] = None) -> dict:
    """KPI cards — SQL aggregates on canonical (patient, doctor) rows for today."""
    _maybe_mark_past_appointments(db)
    today = _today()
    day_start, day_end = _today_range()

    q, Visit = _todays_appointments_query(
        db,
        doctor_id=doctor_id,
        payment_filter=None,
        include_cancelled=False,
    )
    # DISTINCT ON (patient_id, doctor_id) then aggregate — same paid/unpaid rules.
    canonical = (
        q.order_by(
            Appointment.patient_id.asc(),
            Appointment.doctor_id.asc(),
            *_canonical_priority_order(Visit),
        )
        .distinct(Appointment.patient_id, Appointment.doctor_id)
        .with_entities(
            Appointment.id.label("appointment_id"),
            Appointment.status.label("status"),
            Visit.id.label("visit_id"),
            Visit.payment_status.label("payment_status"),
            Visit.grand_total.label("grand_total"),
        )
        .all()
    )

    # Orphan paid visits (no appointment_id) still need enrich for unpaid→paid.
    missing_ids = [r.appointment_id for r in canonical if r.visit_id is None]
    orphan_paid: set[int] = set()
    if missing_ids:
        apts = db.query(Appointment).filter(Appointment.id.in_(missing_ids)).all()
        from Services import appointment_service

        visit_map = appointment_service._load_visits_for_appointments(db, apts)
        for apt_id, visit in visit_map.items():
            if visit is not None and is_visit_paid(visit):
                orphan_paid.add(apt_id)

    total = len(canonical)
    completed = 0
    paid = 0
    unpaid = 0
    for row in canonical:
        st = status_value(row.status)
        if st == AppointmentStatus.completed.value:
            completed += 1
        is_paid = False
        if row.visit_id is not None:
            if (row.payment_status or "") == "paid" or float(row.grand_total or 0) <= 0:
                is_paid = True
        elif row.appointment_id in orphan_paid:
            is_paid = True
        if is_paid:
            paid += 1
        else:
            unpaid += 1

    cancelled_q = db.query(func.count(Appointment.id)).filter(
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at < day_end,
        Appointment.status == AppointmentStatus.cancelled,
    )
    if doctor_id:
        cancelled_q = cancelled_q.filter(Appointment.doctor_id == doctor_id)

    return {
        "total_patients": total,
        "completed": completed,
        "todays_paid_appointments": paid,
        "todays_unpaid_appointments": unpaid,
        "todays_cancelled": int(cancelled_q.scalar() or 0),
    }


def get_today_queue(
    db: Session,
    *,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    patient_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Today's appointments (paid and unpaid); optional appointment status and payment filters."""
    _maybe_mark_past_appointments(db)
    today = _today()
    q, Visit = _todays_appointments_query(
        db,
        doctor_id=doctor_id,
        department_id=department_id,
        payment_filter=None,
        include_cancelled=(status == "cancelled"),
    )
    if doctor_name:
        q = q.filter(_doctor_name_filter(doctor_name))
    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))

    rows, total, page, limit = _page_canonical_board(
        db,
        q,
        Visit,
        partition="patient",
        page=page,
        limit=limit,
        payment_filter=payment_filter,
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
                department_id=appointment.department_id,
                department=dept.name if dept else None,
                queue_date=today,
            )
            for appointment, patient, visit, queue, doc, dept in rows
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
    _maybe_mark_past_appointments(db)
    target_date = queue_date or _today()
    q, Visit = _receptionist_appointments_query(
        db,
        date_from=target_date,
        date_to=target_date,
        doctor_id=doctor_id,
        payment_filter=None,
        include_cancelled=(status == "cancelled"),
    )
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search))

    if page is None or limit is None:
        # No pagination → full board (canonical + orphan visit enrich).
        all_rows = _enrich_rows_with_visits(db, _canonical_rows(q, Visit))
        all_rows = _filter_canonical_rows(
            all_rows, status=None, payment_filter=payment_filter
        )
        rows = sorted(all_rows, key=lambda r: (r[0].scheduled_at, r[0].id))
        total, page, limit = len(rows), 1, len(rows) or 1
    else:
        rows, total, page, limit = _page_canonical_board(
            db,
            q,
            Visit,
            partition="patient",
            page=page,
            limit=limit,
            payment_filter=payment_filter,
        )

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
                department_id=appointment.department_id,
                department=dept.name if dept else None,
                queue_date=target_date,
            )
            for appointment, patient, visit, queue, _doc, dept in rows
        ],
    }


def _queue_history_query(
    db: Session,
    *,
    single_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
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
        department_id=department_id,
        payment_filter=None,
        include_cancelled=(status == "cancelled" or status is None),
    )
    q = _apply_receptionist_status_filter(q, status)
    if search:
        q = q.filter(_appointment_search_filter(search, include_doctor=True))
    return q, Visit, date_from, date_to, payment_filter


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
    department_id: Optional[int] = None,
    status: str | None = None,
    payment_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q, Visit, date_from, date_to, payment_filter = _queue_history_query(
        db,
        single_date=single_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        department_id=department_id,
        status=status,
        payment_filter=payment_filter,
        search=search,
    )

    rows, total, page, limit = _page_canonical_board(
        db,
        q,
        Visit,
        partition="appointment",
        page=page,
        limit=limit,
        payment_filter=payment_filter,
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
            department_id=appointment.department_id,
            department=dept.name if dept else None,
            queue_date=(
                queue.queue_date
                if queue
                else (
                    appointment.scheduled_at.astimezone(IST).date()
                    if appointment.scheduled_at
                    else None
                )
            ),
        )
        for appointment, patient, visit, queue, doc, dept in rows
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


def _build_doctor_slots(
    db: Session,
    doctor_id: int,
    schedule_date: date,
    *,
    booked_hm: set[tuple[int, int]] | None = None,
) -> list[dict]:
    """Slots from Admin OPD settings (hospital default or per-doctor override)."""
    day = datetime.combine(schedule_date, time.min, tzinfo=IST)
    config = opd_settings_svc.resolve_doctor_slot_settings(db, doctor_id)
    weekday = opd_settings_svc.slot_weekday_key(day)
    working_days = {str(d).lower()[:3] for d in (config.get("working_days") or [])}
    if weekday not in working_days:
        return []

    duration = max(5, min(240, int(config.get("slot_duration_minutes") or 30)))

    if booked_hm is None:
        day_start = datetime.combine(schedule_date, time.min, tzinfo=IST)
        day_end = datetime.combine(schedule_date, time.max, tzinfo=IST)
        booked = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at >= day_start,
                Appointment.scheduled_at <= day_end,
                Appointment.status.in_(
                    [AppointmentStatus.scheduled, AppointmentStatus.completed]
                ),
            )
            .all()
        )
        booked_hm = set()
        for apt in booked:
            if apt.scheduled_at is None:
                continue
            apt_ist = apt.scheduled_at.astimezone(IST)
            booked_hm.add((apt_ist.hour, apt_ist.minute))

    slots = []
    for slot_time in opd_settings_svc.iter_slot_datetimes(day, config):
        taken = (slot_time.hour, slot_time.minute) in booked_hm
        end_dt = slot_time + timedelta(minutes=duration)
        slots.append(
            {
                "slot_start": slot_time.strftime("%H:%M"),
                "slot_end": end_dt.strftime("%H:%M"),
                "is_available": not taken,
                "status": "booked" if taken else "available",
            }
        )
    return slots


def _booked_slots_by_doctor(
    db: Session, doctor_ids: list[int], schedule_date: date
) -> dict[int, set[tuple[int, int]]]:
    """One query for booked HH:MM per doctor on a date."""
    if not doctor_ids:
        return {}
    day_start = datetime.combine(schedule_date, time.min, tzinfo=IST)
    day_end = datetime.combine(schedule_date, time.max, tzinfo=IST)
    rows = (
        db.query(Appointment.doctor_id, Appointment.scheduled_at)
        .filter(
            Appointment.doctor_id.in_(doctor_ids),
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at <= day_end,
            Appointment.status.in_(
                [AppointmentStatus.scheduled, AppointmentStatus.completed]
            ),
        )
        .all()
    )
    out: dict[int, set[tuple[int, int]]] = {did: set() for did in doctor_ids}
    for doctor_id, scheduled_at in rows:
        if scheduled_at is None:
            continue
        apt_ist = scheduled_at.astimezone(IST)
        out.setdefault(doctor_id, set()).add((apt_ist.hour, apt_ist.minute))
    return out


def get_doctors_schedule(
    db: Session,
    *,
    schedule_date: date,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    include_slots: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    View-only doctor board for a date (IST).

    Returns active doctors with shift fields from doctor_profiles and that day's
    appointment counts. Filters: doctor_id, department_id, search, page, page_size.
    Slots are built only when include_slots=true (batched booked times).
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

    booked_by_doctor: dict[int, set[tuple[int, int]]] = {}
    if include_slots and doctors:
        booked_by_doctor = _booked_slots_by_doctor(
            db, [d.id for d in doctors], schedule_date
        )

    items = []
    for doctor in doctors:
        profile: DoctorProfile | None = doctor.doctor_profile
        dept: Department | None = doctor.department
        stats = counts.get(doctor.id, empty_stats)
        slots = (
            _build_doctor_slots(
                db,
                doctor.id,
                schedule_date,
                booked_hm=booked_by_doctor.get(doctor.id, set()),
            )
            if include_slots
            else None
        )
        available_count = (
            sum(1 for s in slots if s["is_available"]) if slots else 0
        )
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
                "is_available": True,
                "slots": slots,
                "total_slots": len(slots) if slots else 0,
                "booked_slots": (len(slots) - available_count) if slots else 0,
                "available_slots": available_count,
            }
        )

    return {
        "date": schedule_date,
        "total": total,
        "page": page,
        "page_size": page_size,
        "doctors": items,
    }
