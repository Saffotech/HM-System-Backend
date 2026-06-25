from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.nurse_nursing_notes import NursingNote

from Schemas.nurse_schema import (
    NursingNoteCreate,
    NursingNoteUpdate,
    NursingNoteResponse,
)

IST = ZoneInfo("Asia/Kolkata")


def _serialize_note(note: NursingNote) -> NursingNoteResponse:
    return NursingNoteResponse.model_validate(note).model_copy(
        update={
            "patient_uid": (
                note.patient.patient_uid if note.patient else None
            )
        }
    )


def _note_query(db: Session):
    return db.query(NursingNote).options(
        joinedload(NursingNote.patient)
    )


# ==========================================================
# CREATE NOTE
# ==========================================================

def create_note_service(
    db: Session,
    note_data: NursingNoteCreate,
    nurse_id: int
):

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == note_data.appointment_id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    try:

        note = NursingNote(
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            nurse_id=nurse_id,

            status="active",

            symptoms=note_data.symptoms,
            treatment_response=note_data.treatment_response,
            additional_notes=note_data.additional_notes
        )

        db.add(note)

        db.commit()
        db.refresh(note)
        note = (
            _note_query(db)
            .filter(NursingNote.id == note.id)
            .first()
        )

        return _serialize_note(note)

    except Exception:
        db.rollback()
        raise


# ==========================================================
# UPDATE NOTE
# ==========================================================

def update_note_service(
    db: Session,
    note_id: int,
    note_data: NursingNoteUpdate,
    nurse_id: int,
):

    note = (
        db.query(NursingNote)
        .filter(
            NursingNote.id == note_id
        )
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=404,
            detail="Note not found"
        )

    if note.nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update notes you created",
        )

    try:

        update_data = (
            note_data.model_dump(
                exclude_unset=True
            )
        )

        for field, value in update_data.items():
            setattr(note, field, value)

        if hasattr(note, "updated_at"):
            note.updated_at = datetime.now(IST)

        db.commit()
        db.refresh(note)
        note = (
            _note_query(db)
            .filter(NursingNote.id == note.id)
            .first()
        )

        return _serialize_note(note)

    except Exception:
        db.rollback()
        raise


# ==========================================================
# GET SINGLE NOTE
# ==========================================================

def get_note_by_id_service(
    db: Session,
    note_id: int
):

    note = (
        _note_query(db)
        .filter(
            NursingNote.id == note_id
        )
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=404,
            detail="Note not found"
        )

    return _serialize_note(note)


# ==========================================================
# GET ALL NOTES
# ==========================================================

def get_all_notes_service(
    db: Session,
    page: int = 1,
    page_size: int = 20
):

    notes = (
        _note_query(db)
        .order_by(
            NursingNote.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return [_serialize_note(note) for note in notes]


# ==========================================================
# SEARCH / FILTER NOTES
# ==========================================================

def search_notes_service(
    db: Session,

    patient_id: int | None = None,
    patient_uid: str | None = None,
    appointment_id: int | None = None,

    name: str | None = None,
    phone: str | None = None,

    status: str | None = None,
    nurse_id: int | None = None,

    from_date: date | None = None,
    to_date: date | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = (
        _note_query(db)
        .join(
            Patient,
            Patient.id == NursingNote.patient_id
        )
    )

    if patient_id:
        query = query.filter(
            NursingNote.patient_id == patient_id
        )

    if appointment_id:
        query = query.filter(
            NursingNote.appointment_id == appointment_id
        )

    if name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{name}%"
                ),
                Patient.last_name.ilike(
                    f"%{name}%"
                )
            )
        )

    if phone:
        query = query.filter(
            Patient.phone.ilike(
                f"%{phone}%"
            )
        )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if status:
        query = query.filter(
            NursingNote.status == status
        )

    if nurse_id:
        query = query.filter(
            NursingNote.nurse_id == nurse_id
        )

    if from_date:
        query = query.filter(
            NursingNote.created_at >= from_date
        )

    if to_date:
        query = query.filter(
            NursingNote.created_at <
            (to_date + timedelta(days=1))
        )

    notes = (
        query
        .order_by(
            NursingNote.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return [_serialize_note(note) for note in notes]