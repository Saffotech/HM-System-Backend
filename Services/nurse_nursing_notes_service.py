from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.nurse_nursing_notes import NursingNote, NursingNoteStatus
from Models.patient import Patient
from Schemas.nurse_schema import (
    NursingNoteCreate,
    NursingNoteUpdate,
    NursingNoteResponse,
)
from Services import nurse_helpers as nh


def _note_query(db: Session):
    return db.query(NursingNote).options(
        joinedload(NursingNote.patient),
        joinedload(NursingNote.nurse),
    )


def _serialize_note(
    note: NursingNote,
    *,
    bed_number: str | None = None,
) -> NursingNoteResponse:
    patient = note.patient
    nurse = note.nurse
    return NursingNoteResponse(
        id=note.id,
        appointment_id=note.appointment_id,
        patient_id=note.patient_id,
        patient_uid=patient.patient_uid if patient else None,
        patient_name=nh.patient_display_name(patient),
        bed_number=bed_number,
        nurse_id=note.nurse_id,
        nurse_name=nh.user_display_name(nurse),
        symptoms=note.symptoms,
        treatment_response=note.treatment_response,
        additional_notes=note.additional_notes,
        status=note.status.value if note.status else None,
        created_at=note.created_at,
    )


def _serialize_notes(db: Session, notes: list[NursingNote]) -> list[NursingNoteResponse]:
    if not notes:
        return []
    beds = nh.occupied_beds_map(db, {n.patient_id for n in notes})
    return [
        _serialize_note(
            note,
            bed_number=(
                beds[note.patient_id].bed_number
                if note.patient_id in beds
                else None
            ),
        )
        for note in notes
    ]


def create_note_service(
    db: Session,
    note_data: NursingNoteCreate,
    nurse_id: int,
):
    patient, appointment = nh.resolve_patient_and_appointment(
        db,
        appointment_id=note_data.appointment_id,
        patient_id=note_data.patient_id,
    )

    try:
        note = NursingNote(
            appointment_id=appointment.id if appointment else None,
            patient_id=patient.id,
            nurse_id=nurse_id,
            created_by=nurse_id,
            updated_by=nurse_id,
            status=NursingNoteStatus.ACTIVE,
            symptoms=note_data.symptoms,
            treatment_response=note_data.treatment_response,
            additional_notes=note_data.additional_notes,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        note = _note_query(db).filter(NursingNote.id == note.id).first()
        bed = nh.occupied_bed_for_patient(db, note.patient_id)
        return _serialize_note(
            note,
            bed_number=bed.bed_number if bed else None,
        )
    except Exception:
        db.rollback()
        raise


def update_note_service(
    db: Session,
    note_id: int,
    note_data: NursingNoteUpdate,
    nurse_id: int,
):
    note = db.query(NursingNote).filter(NursingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update notes you created",
        )

    try:
        update_data = note_data.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] is not None:
            try:
                update_data["status"] = NursingNoteStatus(update_data["status"])
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid note status. Use: active, archived",
                ) from exc

        for field, value in update_data.items():
            setattr(note, field, value)

        note.updated_by = nurse_id
        note.updated_at = nh.now_ist()

        db.commit()
        db.refresh(note)
        note = _note_query(db).filter(NursingNote.id == note.id).first()
        bed = nh.occupied_bed_for_patient(db, note.patient_id)
        return _serialize_note(
            note,
            bed_number=bed.bed_number if bed else None,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def get_note_by_id_service(db: Session, note_id: int):
    note = _note_query(db).filter(NursingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    bed = nh.occupied_bed_for_patient(db, note.patient_id)
    return _serialize_note(note, bed_number=bed.bed_number if bed else None)


def get_all_notes_service(db: Session, page: int = 1, page_size: int = 20):
    notes = (
        _note_query(db)
        .order_by(NursingNote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _serialize_notes(db, notes)


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
    page_size: int = 20,
):
    query = _note_query(db).join(Patient, Patient.id == NursingNote.patient_id)

    if patient_id:
        query = query.filter(NursingNote.patient_id == patient_id)
    if appointment_id:
        query = query.filter(NursingNote.appointment_id == appointment_id)
    if name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(f"%{name}%"),
                Patient.last_name.ilike(f"%{name}%"),
            )
        )
    if phone:
        query = query.filter(Patient.phone.ilike(f"%{phone}%"))
    if patient_uid:
        query = query.filter(Patient.patient_uid.ilike(f"%{patient_uid}%"))
    if status:
        query = query.filter(NursingNote.status == status)
    if nurse_id:
        query = query.filter(NursingNote.nurse_id == nurse_id)
    if from_date:
        query = query.filter(NursingNote.created_at >= from_date)
    if to_date:
        query = query.filter(
            NursingNote.created_at < (to_date + timedelta(days=1))
        )

    notes = (
        query.order_by(NursingNote.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _serialize_notes(db, notes)
