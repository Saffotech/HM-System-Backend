"""Read-only clinical views (vitals + nursing notes) for a doctor's assigned patients.

This service is intentionally thin: it verifies the doctor->patient assignment,
builds a read-only query, applies pagination/date filters, and reuses the nurse
serializers. It does NOT duplicate nurse create/update business logic.
"""
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.opd_billing import Appointment
from Models.ipd import IpdAdmission
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_nursing_notes import NursingNote

from Services.nurse_patient_vitals_service import _serialize_vital
from Services.nurse_nursing_notes_service import _serialize_note


def get_assigned_patient_ids(db: Session, doctor_id: int) -> set[int]:
    """Patient IDs linked to the doctor via OPD appointments or IPD admissions."""
    opd_ids = {
        row[0]
        for row in db.query(Appointment.patient_id)
        .filter(Appointment.doctor_id == doctor_id)
        .all()
    }
    ipd_ids = {
        row[0]
        for row in db.query(IpdAdmission.patient_id)
        .filter(IpdAdmission.doctor_id == doctor_id)
        .all()
    }
    return opd_ids | ipd_ids


def _assert_patient_assigned(db: Session, doctor_id: int, patient_id: int) -> None:
    if patient_id not in get_assigned_patient_ids(db, doctor_id):
        raise HTTPException(
            status_code=403,
            detail="Patient is not assigned to this doctor",
        )


def _paginate(query, page: int, page_size: int):
    total = query.count()
    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, rows


def get_patient_vitals_service(
    db: Session,
    doctor_id: int,
    patient_id: int,
    page: int = 1,
    page_size: int = 20,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    _assert_patient_assigned(db, doctor_id, patient_id)

    query = (
        db.query(PatientVitals)
        .options(
            joinedload(PatientVitals.patient),
            joinedload(PatientVitals.nurse),
        )
        .filter(PatientVitals.patient_id == patient_id)
    )

    if from_date:
        query = query.filter(PatientVitals.recorded_at >= from_date)
    if to_date:
        query = query.filter(
            PatientVitals.recorded_at < (to_date + timedelta(days=1))
        )

    query = query.order_by(
        PatientVitals.recorded_at.desc(),
        PatientVitals.id.desc(),
    )

    total, rows = _paginate(query, page, page_size)
    items = [_serialize_vital(vital, db) for vital in rows]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_patient_notes_service(
    db: Session,
    doctor_id: int,
    patient_id: int,
    page: int = 1,
    page_size: int = 20,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    _assert_patient_assigned(db, doctor_id, patient_id)

    query = (
        db.query(NursingNote)
        .options(
            joinedload(NursingNote.patient),
            joinedload(NursingNote.nurse),
        )
        .filter(NursingNote.patient_id == patient_id)
    )

    if from_date:
        query = query.filter(NursingNote.created_at >= from_date)
    if to_date:
        query = query.filter(
            NursingNote.created_at < (to_date + timedelta(days=1))
        )

    query = query.order_by(
        NursingNote.created_at.desc(),
        NursingNote.id.desc(),
    )

    total, rows = _paginate(query, page, page_size)
    items = [_serialize_note(note, db) for note in rows]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
