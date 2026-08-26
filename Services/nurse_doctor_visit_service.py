from datetime import date, datetime
import logging
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Date, cast, func, or_
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.ipd import IpdAdmission
from Models.nurse_doctor_visit import NurseDoctorVisit
from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.role import Role
from Models.user import User
from Enums.notification import NotificationType, ReferenceType, SourceModule
from Schemas.nurse_doctor_visit_schema import (
    DoctorPatientVisitsResponse,
    NurseDoctorListResponse,
    NurseDoctorOption,
    NurseDoctorVisitCreate,
    NurseDoctorVisitListResponse,
    NurseDoctorVisitResponse,
    NurseDoctorVisitUpdate,
    NurseDoctorVisitVoidRequest,
)
from Services import opd_helpers as h
from Services.doctor_helpers import day_bounds
from Services.ipd_helpers import doctor_display
from Services.nurse_nursing_notes_service import _resolve_patient_and_appointment
from Services.notification_service import create_notification
from Utils.pagination import paginate_sequence

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(IST)


def _user_display_name(user: User | None) -> str:
    if not user:
        return ""
    return f"{user.first_name} {user.last_name or ''}".strip()


def _notify_doctor_visit(
    db: Session,
    visit: NurseDoctorVisit,
    nurse: User,
    *,
    action: str,
) -> None:
    try:
        patient_name = _patient_display_name(visit.patient) or f"Patient #{visit.patient_id}"
        notification_type = {
            "recorded": NotificationType.NURSE_DOCTOR_VISIT_CREATED,
            "updated": NotificationType.NURSE_DOCTOR_VISIT_UPDATED,
            "voided": NotificationType.NURSE_DOCTOR_VISIT_VOIDED,
        }[action]
        create_notification(
            db,
            user_id=visit.doctor_id,
            title=f"Doctor visit {action}",
            message=f"{nurse.first_name} {nurse.last_name or ''}".strip()
            + f" {action} a doctor visit for {patient_name}.",
            notification_type=notification_type,
            source_module=SourceModule.NURSE,
            reference_type=ReferenceType.PATIENT,
            reference_id=visit.patient_id,
            created_by=nurse.id,
            created_by_name=_user_display_name(nurse),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to send doctor visit notification for visit %s",
            visit.id,
        )


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


def _active_doctor(db: Session, doctor_id: int) -> User:
    doctor = (
        db.query(User)
        .options(joinedload(User.department))
        .join(Role, User.role_id == Role.id)
        .filter(
            User.id == doctor_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.name == h.DOCTOR_ROLE,
        )
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


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


def _resolve_visit_department(
    db: Session,
    doctor: User,
    department_id: int | None = None,
) -> tuple[int | None, str | None]:
    """Snapshot the department selected for this visit.

    Frontend currently sends doctor_id only. Use the doctor's department,
    or an explicit department_id when provided.
    """
    if department_id is not None:
        department = _active_department(db, department_id)
        if doctor.department_id and doctor.department_id != department.id:
            raise HTTPException(
                status_code=400,
                detail="Doctor does not belong to the selected department",
            )
        return department.id, department.name

    department = doctor.department
    if department is None and doctor.department_id:
        department = (
            db.query(Department)
            .filter(Department.id == doctor.department_id)
            .first()
        )
    if department:
        return department.id, department.name
    return None, None


def _visit_query(db: Session):
    return (
        db.query(NurseDoctorVisit)
        .options(
            joinedload(NurseDoctorVisit.patient),
            joinedload(NurseDoctorVisit.doctor).joinedload(User.department),
            joinedload(NurseDoctorVisit.department),
        )
        .filter(NurseDoctorVisit.is_voided.is_(False))
    )


def _visit_date_filter(query, visit_date: date | None):
    if visit_date is None:
        return query
    start, end = day_bounds(visit_date)
    return query.filter(
        NurseDoctorVisit.visited_at >= start,
        NurseDoctorVisit.visited_at <= end,
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
        return query.filter(NurseDoctorVisit.patient_id == -1)

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
        return query.filter(NurseDoctorVisit.patient_id == -1)
    return query.filter(NurseDoctorVisit.patient_id.in_(patient_ids))


def _assign_visit_numbers(
    visits: list[NurseDoctorVisit],
) -> dict[int, int]:
    """visit_number keyed by visit id — same patient/date batches only."""
    ordered = sorted(visits, key=lambda row: (row.visited_at, row.id))
    return {row.id: index for index, row in enumerate(ordered, start=1)}


def _serialize_visit(
    visit: NurseDoctorVisit,
    *,
    visit_number: int | None = None,
) -> NurseDoctorVisitResponse:
    patient = visit.patient
    doctor = visit.doctor
    department_id = visit.department_id
    department_name = visit.department_name
    if not department_name:
        live_dept = getattr(visit, "department", None) or getattr(doctor, "department", None)
        if live_dept:
            department_id = department_id or live_dept.id
            department_name = live_dept.name
    return NurseDoctorVisitResponse(
        id=visit.id,
        patient_id=visit.patient_id,
        patient_uid=getattr(patient, "patient_uid", None),
        patient_name=_patient_display_name(patient),
        doctor_id=visit.doctor_id,
        doctor_name=visit.doctor_name,
        department_id=department_id,
        department_name=department_name,
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
    visits: list[NurseDoctorVisit],
) -> list[NurseDoctorVisitResponse]:
    numbers = _assign_visit_numbers(visits)
    return [
        _serialize_visit(visit, visit_number=numbers.get(visit.id))
        for visit in visits
    ]


def create_doctor_visit_service(
    db: Session,
    payload: NurseDoctorVisitCreate,
    nurse: User,
) -> NurseDoctorVisitResponse:
    patient, _appointment = _resolve_patient_and_appointment(
        db,
        appointment_id=payload.appointment_id,
        patient_id=payload.patient_id,
    )
    doctor = _active_doctor(db, payload.doctor_id)
    department_id, department_name = _resolve_visit_department(
        db,
        doctor,
        payload.department_id,
    )

    visit = NurseDoctorVisit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        doctor_name=doctor_display(db, doctor.id) or _user_display_name(doctor),
        department_id=department_id,
        department_name=department_name,
        visited_at=_parse_visited_at(payload.visited_at),
        notes=(payload.notes or "").strip() or None,
        recorded_by=nurse.id,
        recorded_by_name=_user_display_name(nurse),
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    visit = _visit_query(db).filter(NurseDoctorVisit.id == visit.id).first()
    _notify_doctor_visit(db, visit, nurse, action="recorded")
    day = visit.visited_at.astimezone(IST).date()
    same_day = (
        _visit_date_filter(
            _visit_query(db).filter(NurseDoctorVisit.patient_id == visit.patient_id),
            day,
        )
        .order_by(NurseDoctorVisit.visited_at.asc(), NurseDoctorVisit.id.asc())
        .all()
    )
    numbers = _assign_visit_numbers(same_day)
    return _serialize_visit(visit, visit_number=numbers.get(visit.id))


def list_doctor_visits_service(
    db: Session,
    *,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    doctor_id: int | None = None,
    visit_date: date | None = None,
    search: str | None = None,
    allocated_only: bool = False,
    allocation_nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> NurseDoctorVisitListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    ist_day = cast(
        func.timezone("Asia/Kolkata", NurseDoctorVisit.visited_at),
        Date,
    )
    row_number = func.row_number().over(
        partition_by=(NurseDoctorVisit.patient_id, ist_day),
        order_by=(
            NurseDoctorVisit.visited_at.asc(),
            NurseDoctorVisit.id.asc(),
        ),
    ).label("visit_number")
    numbered = (
        db.query(NurseDoctorVisit.id.label("id"), row_number)
        .filter(NurseDoctorVisit.is_voided.is_(False))
        .subquery()
    )

    query = (
        db.query(NurseDoctorVisit, numbered.c.visit_number)
        .join(numbered, numbered.c.id == NurseDoctorVisit.id)
        .options(
            joinedload(NurseDoctorVisit.patient),
            joinedload(NurseDoctorVisit.doctor).joinedload(User.department),
            joinedload(NurseDoctorVisit.department),
        )
        .filter(NurseDoctorVisit.is_voided.is_(False))
    )
    joined_patient = False

    if patient_id:
        query = query.filter(NurseDoctorVisit.patient_id == patient_id)

    if patient_uid:
        query = query.join(Patient, Patient.id == NurseDoctorVisit.patient_id)
        joined_patient = True
        query = query.filter(
            Patient.patient_uid.ilike(f"%{patient_uid.strip()}%")
        )

    if doctor_id:
        query = query.filter(NurseDoctorVisit.doctor_id == doctor_id)

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
            query = query.join(Patient, Patient.id == NurseDoctorVisit.patient_id)
            joined_patient = True
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                NurseDoctorVisit.doctor_name.ilike(term),
                NurseDoctorVisit.department_name.ilike(term),
                NurseDoctorVisit.notes.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(
            NurseDoctorVisit.visited_at.desc(),
            NurseDoctorVisit.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        _serialize_visit(visit, visit_number=visit_number)
        for visit, visit_number in rows
    ]

    return NurseDoctorVisitListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


def update_doctor_visit_service(
    db: Session,
    visit_id: int,
    payload: NurseDoctorVisitUpdate,
    nurse: User,
) -> NurseDoctorVisitResponse:
    visit = db.query(NurseDoctorVisit).filter(NurseDoctorVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Doctor visit not found")
    if visit.is_voided:
        raise HTTPException(status_code=400, detail="Cannot edit a voided visit")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "doctor_id" in update_data:
        doctor = _active_doctor(db, update_data["doctor_id"])
        visit.doctor_id = doctor.id
        visit.doctor_name = doctor_display(db, doctor.id) or _user_display_name(doctor)
        next_department_id = update_data.get("department_id")
        visit.department_id, visit.department_name = _resolve_visit_department(
            db,
            doctor,
            next_department_id,
        )
    elif "department_id" in update_data:
        doctor = _active_doctor(db, visit.doctor_id)
        visit.department_id, visit.department_name = _resolve_visit_department(
            db,
            doctor,
            update_data["department_id"],
        )

    if "visited_at" in update_data:
        visit.visited_at = _parse_visited_at(update_data["visited_at"])

    if "notes" in update_data:
        visit.notes = (update_data["notes"] or "").strip() or None

    visit.updated_by = nurse.id
    visit.updated_by_name = _user_display_name(nurse)
    visit.updated_at = _now()

    db.commit()
    db.refresh(visit)

    visit = _visit_query(db).filter(NurseDoctorVisit.id == visit.id).first()
    _notify_doctor_visit(db, visit, nurse, action="updated")
    day = visit.visited_at.astimezone(IST).date()
    same_day = (
        _visit_date_filter(
            _visit_query(db).filter(NurseDoctorVisit.patient_id == visit.patient_id),
            day,
        )
        .order_by(NurseDoctorVisit.visited_at.asc(), NurseDoctorVisit.id.asc())
        .all()
    )
    numbers = _assign_visit_numbers(same_day)
    return _serialize_visit(visit, visit_number=numbers.get(visit.id))


def void_doctor_visit_service(
    db: Session,
    visit_id: int,
    payload: NurseDoctorVisitVoidRequest,
    nurse: User,
) -> NurseDoctorVisitResponse:
    visit = db.query(NurseDoctorVisit).filter(NurseDoctorVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Doctor visit not found")
    if visit.is_voided:
        raise HTTPException(status_code=400, detail="Visit is already voided")

    visit.is_voided = True
    visit.voided_by = nurse.id
    visit.voided_by_name = _user_display_name(nurse)
    visit.voided_at = _now()
    visit.void_reason = payload.void_reason.strip()

    db.commit()
    db.refresh(visit)
    _notify_doctor_visit(db, visit, nurse, action="voided")
    return _serialize_visit(visit, visit_number=None)


def list_active_doctors_service(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> NurseDoctorListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(User)
        .options(joinedload(User.department))
        .join(Role, User.role_id == Role.id)
        .outerjoin(Department, User.department_id == Department.id)
        .filter(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.name == h.DOCTOR_ROLE,
        )
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.specialization.ilike(term),
                Department.name.ilike(term),
            )
        )

    total = query.count()
    doctors = (
        query.order_by(User.first_name.asc(), User.last_name.asc(), User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        NurseDoctorOption(
            id=doctor.id,
            name=h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. "),
            specialization=doctor.specialization
            or (doctor.department.name if doctor.department else None),
            department_id=doctor.department_id,
            department_name=doctor.department.name if doctor.department else None,
        )
        for doctor in doctors
    ]

    return NurseDoctorListResponse(
        total=total,
        page=page,
        page_size=page_size,
        doctors=items,
    )


def _doctor_can_view_patient(db: Session, doctor_id: int, patient_id: int) -> bool:
    admitted = (
        db.query(IpdAdmission.id)
        .filter(
            IpdAdmission.patient_id == patient_id,
            IpdAdmission.doctor_id == doctor_id,
            IpdAdmission.status == "admitted",
        )
        .first()
    )
    if admitted:
        return True

    appointment = (
        db.query(Appointment.id)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status != "cancelled",
        )
        .first()
    )
    return appointment is not None


def get_doctor_patient_visits_service(
    db: Session,
    *,
    doctor_id: int,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    visit_date: date | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> DoctorPatientVisitsResponse:
    if not patient_id and not patient_uid:
        raise HTTPException(
            status_code=400,
            detail="Provide patient_id or patient_uid",
        )

    patient_query = db.query(Patient).filter(Patient.is_active.is_(True))
    if patient_id:
        patient_query = patient_query.filter(Patient.id == patient_id)
    if patient_uid:
        patient_query = patient_query.filter(
            Patient.patient_uid.ilike(patient_uid.strip())
        )
    patient = patient_query.first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not _doctor_can_view_patient(db, doctor_id, patient.id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view visits for this patient",
        )

    on_date = visit_date or _now().date()
    visits = (
        _visit_date_filter(
            _visit_query(db).filter(NurseDoctorVisit.patient_id == patient.id),
            on_date,
        )
        .order_by(NurseDoctorVisit.visited_at.asc(), NurseDoctorVisit.id.asc())
        .all()
    )
    numbers = _assign_visit_numbers(visits)
    serialized = [
        _serialize_visit(visit, visit_number=numbers.get(visit.id))
        for visit in visits
    ]

    items, total, page_n, size = paginate_sequence(
        serialized, page=page, page_size=page_size
    )
    payload = DoctorPatientVisitsResponse(
        patient_id=patient.id,
        patient_uid=patient.patient_uid,
        patient_name=_patient_display_name(patient),
        visit_date=on_date,
        visit_count=total,
        visits=items,
    )
    if page is not None:
        payload.page = page_n
        payload.page_size = size
        payload.total = total
    return payload
