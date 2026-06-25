from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, Bed
from Models.patient import Patient
from Models.nurse_nursing_notes import NursingNote

from Schemas.nurse_schema import (
    NursingNoteCreate,
    NursingNoteUpdate
)

IST = ZoneInfo("Asia/Kolkata")


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name} {user.last_name or ''}".strip()


def _patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return f"{patient.first_name} {patient.last_name or ''}".strip()


def _enrich_note(db: Session, note: NursingNote) -> NursingNote:
    patient = (
        db.query(Patient)
        .filter(Patient.id == note.patient_id)
        .first()
    )
    if patient:
        note.patient_uid = patient.patient_uid
        note.patient_name = _patient_display_name(patient)

    bed = (
        db.query(Bed)
        .filter(
            Bed.patient_id == note.patient_id,
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .first()
    )
    if bed:
        note.bed_number = bed.bed_number

    nurse = (
        db.query(User)
        .filter(User.id == note.nurse_id)
        .first()
    )
    if nurse:
        note.nurse_name = _user_display_name(nurse)

    return note


def _enrich_notes_batch(
    db: Session,
    notes: list[NursingNote],
) -> list[NursingNote]:
    if not notes:
        return notes

    patient_ids = {n.patient_id for n in notes}
    nurse_ids = {n.nurse_id for n in notes}

    patients = {
        p.id: p
        for p in db.query(Patient)
        .filter(Patient.id.in_(patient_ids))
        .all()
    }
    nurses = {
        u.id: u
        for u in db.query(User)
        .filter(User.id.in_(nurse_ids))
        .all()
    }
    beds = {}
    for bed in (
        db.query(Bed)
        .filter(
            Bed.patient_id.in_(patient_ids),
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .all()
    ):
        if bed.patient_id not in beds:
            beds[bed.patient_id] = bed

    for note in notes:
        patient = patients.get(note.patient_id)
        if patient:
            note.patient_uid = patient.patient_uid
            note.patient_name = _patient_display_name(patient)

        bed = beds.get(note.patient_id)
        if bed:
            note.bed_number = bed.bed_number

        nurse = nurses.get(note.nurse_id)
        if nurse:
            note.nurse_name = _user_display_name(nurse)

    return notes


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

        return note

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

        return note

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

    return note


# ==========================================================
# GET ALL NOTES
# ==========================================================

def get_all_notes_service(
    db: Session,
    page: int = 1,
    page_size: int = 20
):

    return (
        db.query(NursingNote)
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


# ==========================================================
# SEARCH / FILTER NOTES
# ==========================================================

def search_notes_service(
    db: Session,

    patient_id: int | None = None,
    appointment_id: int | None = None,

    name: str | None = None,
    phone: str | None = None,
    uhid: str | None = None,

    status: str | None = None,
    nurse_id: int | None = None,

    from_date: date | None = None,
    to_date: date | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = (
        db.query(NursingNote)
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

    if uhid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{uhid}%"
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

    return (
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