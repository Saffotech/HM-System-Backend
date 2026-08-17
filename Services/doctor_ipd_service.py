from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from Models.ipd import IpdAdmission
from Models.patient import Patient
from Services import doctor_helpers as h

_STATUS_ALIASES = {
    "admit": "admitted",
    "admitted": "admitted",
    "discharge": "discharged",
    "discharged": "discharged",
    "cancelled": "cancelled",
}


def normalize_ipd_status(status: Optional[str]) -> Optional[str]:
    """Map UI aliases (admit/discharge) to DB status. None means no status filter."""
    if status is None:
        return "admitted"
    key = str(status).strip().lower()
    if not key or key == "admitted":
        return "admitted"
    if key == "all":
        return None
    mapped = _STATUS_ALIASES.get(key)
    if mapped is None:
        raise HTTPException(
            status_code=400,
            detail="status must be admitted, discharged, cancelled, or all",
        )
    return mapped


def list_doctor_ipd_admissions_service(
    db: Session,
    doctor_id: int,
    *,
    status: Optional[str] = "admitted",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    db_status = normalize_ipd_status(status)

    query = (
        db.query(IpdAdmission)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
        .filter(
            IpdAdmission.doctor_id == doctor_id,
            Patient.is_active.is_(True),
        )
    )
    if db_status:
        query = query.filter(IpdAdmission.status == db_status)

    date_clause = h.admitted_between(from_date, to_date)
    if date_clause is not None:
        query = query.filter(date_clause)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                Patient.phone.ilike(term),
                IpdAdmission.admission_no.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(IpdAdmission.admitted_at.desc(), IpdAdmission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": h.admissions_to_dicts(db, rows, use_dashboard_status=False),
    }
