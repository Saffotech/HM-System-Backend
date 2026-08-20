from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.patient import Patient
from Models.nurse_other_visit import PatientOtherVisit
from Models.user import User
from Schemas.nurse_other_visit_schema import (
    DepartmentListResponse,
    DepartmentOption,
    OtherVisitCreate,
    OtherVisitListResponse,
    OtherVisitResponse,
    OtherVisitUpdate,
    OtherVisitVoidRequest,
)
from Services.doctor_helpers import day_bounds
from Services.nurse_nursing_notes_service import _resolve_patient_and_appointment

IST = ZoneInfo("Asia/Kolkata")


def _now() -> datetime:
    return datetime.now(IST)


def _user_display_name(user: User | None) -> str:
    if not user:
        return ""
    return f"{user.first_name} {user.last_name or ''}".strip()


def _patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return f"{patient.first_name} {patient.last_name or ''}".strip()


def _parse_visited_at(value: datetime | None) -> datetime:
    if value is None:
        return _now()
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


def _active_department(db: Session, department_id: int) -> Department:
    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.is_active.is_(True),
        )
        .first()
    )
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


def _visit_query(db: Session):
    return (
        db.query(PatientOtherVisit)
        .options(
            joinedload(PatientOtherVisit.patient),
            joinedload(PatientOtherVisit.department),
        )
        .filter(PatientOtherVisit.is_voided.is_(False))
    )


def _visit_date_filter(query, visit_date: date | None):
    if visit_date is None:
        return query
    start, end = day_bounds(visit_date)
    return query.filter(
        PatientOtherVisit.visited_at >= start,
        PatientOtherVisit.visited_at <= end,
    )


def _apply_allocated_only_filter(
    db: Session,
    query,
    *,
    allocated_only: bool,
    nurse_id: int | None,
    assignment_date=None,
    shift_name: str | None = None,
):
    if not allocated_only:
        return query
    if nurse_id is None:
        return query.filter(PatientOtherVisit.patient_id == -1)

    from Services.nurse_shift_bed_allocation_service import (
        get_allocated_patient_ids_for_nurse,
    )

    patient_ids = get_allocated_patient_ids_for_nurse(
        db,
        nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    if not patient_ids:
        return query.filter(PatientOtherVisit.patient_id == -1)
    return query.filter(PatientOtherVisit.patient_id.in_(patient_ids))


def _assign_visit_numbers(
    visits: list[PatientOtherVisit],
) -> dict[int, int]:
    """visit_number keyed by visit id — same patient/date batches only."""
    ordered = sorted(visits, key=lambda row: (row.visited_at, row.id))
    return {row.id: index for index, row in enumerate(ordered, start=1)}


def _serialize_visit(
    visit: PatientOtherVisit,
    *,
    visit_number: int | None = None,
) -> OtherVisitResponse:
    patient = visit.patient
    return OtherVisitResponse(
        id=visit.id,
        patient_id=visit.patient_id,
        patient_uid=getattr(patient, "patient_uid", None),
        patient_name=_patient_display_name(patient),
        department_id=visit.department_id,
        department_name=visit.department_name,
        person_name=visit.person_name,
        visited_at=visit.visited_at,
        notes=visit.notes,
        visit_number=visit_number,
        recorded_by=visit.recorded_by,
        recorded_by_name=visit.recorded_by_name,
        created_at=visit.created_at,
        updated_by=visit.updated_by,
        updated_by_name=visit.updated_by_name,
        updated_at=visit.updated_at,
        is_voided=visit.is_voided,
    )


def _serialize_visits_with_numbers(
    visits: list[PatientOtherVisit],
) -> list[OtherVisitResponse]:
    numbers = _assign_visit_numbers(visits)
    return [
        _serialize_visit(visit, visit_number=numbers.get(visit.id))
        for visit in visits
    ]


def _group_visit_numbers_by_patient_date(
    db: Session,
    visits: list[PatientOtherVisit],
) -> dict[int, int]:
    """Compute visit_number per visit id across patient+date groups."""
    if not visits:
        return {}

    groups: dict[tuple[int, date], list[PatientOtherVisit]] = {}
    for visit in visits:
        local_day = visit.visited_at.astimezone(IST).date()
        key = (visit.patient_id, local_day)
        groups.setdefault(key, []).append(visit)

    numbers: dict[int, int] = {}
    for group_visits in groups.values():
        numbers.update(_assign_visit_numbers(group_visits))
    return numbers


def create_other_visit_service(
    db: Session,
    payload: OtherVisitCreate,
    nurse: User,
) -> OtherVisitResponse:
    patient, _appointment = _resolve_patient_and_appointment(
        db,
        appointment_id=None,
        patient_id=payload.patient_id,
    )
    department = _active_department(db, payload.department_id)
    person_name = payload.person_name.strip()
    if not person_name:
        raise HTTPException(status_code=400, detail="person_name is required")

    visit = PatientOtherVisit(
        patient_id=patient.id,
        department_id=department.id,
        department_name=department.name,
        person_name=person_name,
        visited_at=_parse_visited_at(payload.visited_at),
        notes=(payload.notes or "").strip() or None,
        recorded_by=nurse.id,
        recorded_by_name=_user_display_name(nurse),
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    visit = _visit_query(db).filter(PatientOtherVisit.id == visit.id).first()
    day = visit.visited_at.astimezone(IST).date()
    same_day = (
        _visit_date_filter(
            _visit_query(db).filter(PatientOtherVisit.patient_id == visit.patient_id),
            day,
        )
        .order_by(PatientOtherVisit.visited_at.asc(), PatientOtherVisit.id.asc())
        .all()
    )
    numbers = _assign_visit_numbers(same_day)
    return _serialize_visit(visit, visit_number=numbers.get(visit.id))


def list_other_visits_service(
    db: Session,
    *,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    department_id: int | None = None,
    visit_date: date | None = None,
    search: str | None = None,
    allocated_only: bool = False,
    allocation_nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OtherVisitListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = _visit_query(db)
    joined_patient = False

    if patient_id:
        query = query.filter(PatientOtherVisit.patient_id == patient_id)

    if patient_uid:
        query = query.join(Patient, Patient.id == PatientOtherVisit.patient_id)
        joined_patient = True
        query = query.filter(
            Patient.patient_uid.ilike(f"%{patient_uid.strip()}%")
        )

    if department_id:
        query = query.filter(PatientOtherVisit.department_id == department_id)

    query = _visit_date_filter(query, visit_date)

    query = _apply_allocated_only_filter(
        db,
        query,
        allocated_only=allocated_only,
        nurse_id=allocation_nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        if not joined_patient:
            query = query.join(Patient, Patient.id == PatientOtherVisit.patient_id)
            joined_patient = True
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                PatientOtherVisit.department_name.ilike(term),
                PatientOtherVisit.person_name.ilike(term),
                PatientOtherVisit.notes.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(
            PatientOtherVisit.visited_at.desc(),
            PatientOtherVisit.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if patient_id and visit_date:
        all_for_day = (
            _visit_date_filter(
                _visit_query(db).filter(PatientOtherVisit.patient_id == patient_id),
                visit_date,
            )
            .order_by(PatientOtherVisit.visited_at.asc(), PatientOtherVisit.id.asc())
            .all()
        )
        numbers = _assign_visit_numbers(all_for_day)
        items = [
            _serialize_visit(row, visit_number=numbers.get(row.id))
            for row in rows
        ]
    else:
        numbers = _group_visit_numbers_by_patient_date(db, rows)
        items = [
            _serialize_visit(row, visit_number=numbers.get(row.id))
            for row in rows
        ]

    return OtherVisitListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


def update_other_visit_service(
    db: Session,
    visit_id: int,
    payload: OtherVisitUpdate,
    nurse: User,
) -> OtherVisitResponse:
    visit = (
        db.query(PatientOtherVisit)
        .filter(PatientOtherVisit.id == visit_id)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Other visit not found")
    if visit.is_voided:
        raise HTTPException(status_code=400, detail="Cannot edit a voided visit")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "department_id" in update_data:
        department = _active_department(db, update_data["department_id"])
        visit.department_id = department.id
        visit.department_name = department.name

    if "person_name" in update_data:
        person_name = (update_data["person_name"] or "").strip()
        if not person_name:
            raise HTTPException(status_code=400, detail="person_name is required")
        visit.person_name = person_name

    if "visited_at" in update_data:
        visit.visited_at = _parse_visited_at(update_data["visited_at"])

    if "notes" in update_data:
        visit.notes = (update_data["notes"] or "").strip() or None

    visit.updated_by = nurse.id
    visit.updated_by_name = _user_display_name(nurse)
    visit.updated_at = _now()

    db.commit()
    db.refresh(visit)

    visit = _visit_query(db).filter(PatientOtherVisit.id == visit.id).first()
    day = visit.visited_at.astimezone(IST).date()
    same_day = (
        _visit_date_filter(
            _visit_query(db).filter(PatientOtherVisit.patient_id == visit.patient_id),
            day,
        )
        .order_by(PatientOtherVisit.visited_at.asc(), PatientOtherVisit.id.asc())
        .all()
    )
    numbers = _assign_visit_numbers(same_day)
    return _serialize_visit(visit, visit_number=numbers.get(visit.id))


def void_other_visit_service(
    db: Session,
    visit_id: int,
    payload: OtherVisitVoidRequest,
    nurse: User,
) -> OtherVisitResponse:
    visit = (
        db.query(PatientOtherVisit)
        .filter(PatientOtherVisit.id == visit_id)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Other visit not found")
    if visit.is_voided:
        raise HTTPException(status_code=400, detail="Visit is already voided")

    visit.is_voided = True
    visit.voided_by = nurse.id
    visit.voided_by_name = _user_display_name(nurse)
    visit.voided_at = _now()
    visit.void_reason = payload.void_reason.strip()

    db.commit()
    db.refresh(visit)
    return _serialize_visit(visit, visit_number=None)


def list_departments_service(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> DepartmentListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = db.query(Department).filter(Department.is_active.is_(True))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Department.name.ilike(term),
                Department.code.ilike(term),
            )
        )

    total = query.count()
    departments = (
        query.order_by(Department.name.asc(), Department.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        DepartmentOption(
            id=department.id,
            name=department.name,
            code=department.code,
        )
        for department in departments
    ]

    return DepartmentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        departments=items,
    )
