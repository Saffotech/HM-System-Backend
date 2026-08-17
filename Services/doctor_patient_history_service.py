from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import extract, or_
from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission
from Models.opd_billing import Appointment
from Models.patient import Patient
from Services import doctor_helpers as h

_ENCOUNTER_TYPES = frozenset({"opd", "ipd", "all"})


def _normalize_encounter_type(encounter_type: Optional[str]) -> str:
    value = (encounter_type or "all").strip().lower()
    if value not in _ENCOUNTER_TYPES:
        raise HTTPException(
            status_code=400,
            detail="encounter_type must be opd, ipd, or all",
        )
    return value


def _patient_search_clause(search: Optional[str]):
    if not search or not search.strip():
        return None
    term = f"%{search.strip()}%"
    return or_(
        Patient.first_name.ilike(term),
        Patient.last_name.ilike(term),
        Patient.patient_uid.ilike(term),
        Patient.phone.ilike(term),
    )


def _apply_opd_date_filters(query, filter_date: Optional[date], month: Optional[int], year: Optional[int]):
    if filter_date:
        return query.filter(h.scheduled_on_date(filter_date))
    if month and year:
        return query.filter(
            extract("month", Appointment.scheduled_at) == month,
            extract("year", Appointment.scheduled_at) == year,
        )
    if year:
        return query.filter(extract("year", Appointment.scheduled_at) == year)
    return query


def _apply_ipd_date_filters(query, filter_date: Optional[date], month: Optional[int], year: Optional[int]):
    if filter_date:
        return query.filter(h.admitted_on_date(filter_date))
    if month and year:
        return query.filter(
            extract("month", IpdAdmission.admitted_at) == month,
            extract("year", IpdAdmission.admitted_at) == year,
        )
    if year:
        return query.filter(extract("year", IpdAdmission.admitted_at) == year)
    return query


def _opd_history_query(
    db: Session,
    doctor_id: int,
    *,
    search: Optional[str] = None,
    patient_uid: Optional[str] = None,
):
    query = (
        db.query(Appointment, Patient)
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed",
            Patient.is_active.is_(True),
        )
    )
    if patient_uid:
        query = query.filter(Patient.patient_uid == patient_uid)
    search_clause = _patient_search_clause(search)
    if search_clause is not None:
        query = query.filter(search_clause)
    return query


def _ipd_history_query(
    db: Session,
    doctor_id: int,
    *,
    search: Optional[str] = None,
    patient_uid: Optional[str] = None,
):
    query = (
        db.query(IpdAdmission, Patient)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
        .filter(
            IpdAdmission.doctor_id == doctor_id,
            IpdAdmission.status == "discharged",
            Patient.is_active.is_(True),
        )
    )
    if patient_uid:
        query = query.filter(Patient.patient_uid == patient_uid)
    search_clause = _patient_search_clause(search)
    if search_clause is not None:
        query = query.filter(search_clause)
    return query


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=h.IST)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=h.IST)
    return dt


def _history_items(db: Session, opd_rows, ipd_rows) -> list[dict]:
    paired = []
    for apt, patient in opd_rows:
        paired.append((_aware(apt.scheduled_at), h.appointment_to_dict(db, apt, patient)))
    for admission, patient in ipd_rows:
        sort_dt = admission.discharged_at or admission.admitted_at
        paired.append(
            (
                _aware(sort_dt),
                h.admission_to_dict(db, admission, patient, use_dashboard_status=False),
            )
        )
    paired.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in paired]


def _paginated(items: list[dict], page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start : start + page_size],
    }


def get_patients_service(
    db: Session,
    doctor_id: int,
    page: int,
    page_size: int,
    filter_date: date = None,
    month: int = None,
    year: int = None,
    search: str = None,
    encounter_type: str = None,
) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    kind = _normalize_encounter_type(encounter_type)

    opd_query = None
    ipd_query = None
    if kind in ("opd", "all"):
        opd_query = _apply_opd_date_filters(
            _opd_history_query(db, doctor_id, search=search),
            filter_date,
            month,
            year,
        )
    if kind in ("ipd", "all"):
        ipd_query = _apply_ipd_date_filters(
            _ipd_history_query(db, doctor_id, search=search),
            filter_date,
            month,
            year,
        )

    if kind == "opd":
        total = opd_query.count()
        rows = (
            opd_query.order_by(Appointment.scheduled_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [h.appointment_to_dict(db, apt, patient) for apt, patient in rows],
        }

    if kind == "ipd":
        total = ipd_query.count()
        rows = (
            ipd_query.order_by(
                IpdAdmission.discharged_at.desc(),
                IpdAdmission.admitted_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                h.admission_to_dict(db, admission, patient, use_dashboard_status=False)
                for admission, patient in rows
            ],
        }

    opd_rows = opd_query.order_by(Appointment.scheduled_at.desc()).all()
    ipd_rows = ipd_query.order_by(IpdAdmission.admitted_at.desc()).all()
    return _paginated(_history_items(db, opd_rows, ipd_rows), page, page_size)


def get_patient_details_service(
    db: Session,
    doctor_id: int,
    patient_uid: str,
    page: int = 1,
    page_size: int = 20,
    encounter_type: str = None,
) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    kind = _normalize_encounter_type(encounter_type)

    opd_query = _opd_history_query(db, doctor_id, patient_uid=patient_uid)
    ipd_query = _ipd_history_query(db, doctor_id, patient_uid=patient_uid)

    if kind == "opd":
        total = opd_query.count()
        rows = (
            opd_query.order_by(Appointment.scheduled_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        visits = [h.appointment_to_dict(db, apt, patient) for apt, patient in rows]
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": visits,
            "patient_history": visits,
        }

    if kind == "ipd":
        total = ipd_query.count()
        rows = (
            ipd_query.order_by(
                IpdAdmission.discharged_at.desc(),
                IpdAdmission.admitted_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        visits = [
            h.admission_to_dict(db, admission, patient, use_dashboard_status=False)
            for admission, patient in rows
        ]
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": visits,
            "patient_history": visits,
        }

    items = _history_items(
        db,
        opd_query.order_by(Appointment.scheduled_at.desc()).all(),
        ipd_query.order_by(IpdAdmission.admitted_at.desc()).all(),
    )
    paged = _paginated(items, page, page_size)
    paged["patient_history"] = paged["items"]
    return paged
