from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from Models.user import User
from Models.opd_billing import Appointment, Bed
from Models.patient import Patient
from Models.nurse_nursing_notes import NursingNote, NursingNoteStatus

from Schemas.nurse_schema import (
    NursingNoteCreate,
    NursingNoteUpdate,
    NursingNoteResponse,
)

IST = ZoneInfo("Asia/Kolkata")


def _paginate_notes(
    db: Session,
    query,
    *,
    page: int,
    page_size: int,
    latest_per_patient: bool,
):
    """
    Registry lists use latest_per_patient=True (one row per patient).
    Patient timeline / filtered history keep latest_per_patient=False (all rows).
    Detail payload includes full history across create notes for the patient.
    """
    if not latest_per_patient:
        notes = (
            query.order_by(NursingNote.created_at.desc(), NursingNote.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        notes = _enrich_notes_batch(db, notes)
        return [_serialize_note(note, db) for note in notes]

    latest_subq = (
        query.enable_eagerloads(False)
        .order_by(None)
        .with_entities(
            NursingNote.patient_id.label("patient_id"),
            func.max(NursingNote.id).label("max_id"),
        )
        .group_by(NursingNote.patient_id)
        .subquery()
    )
    notes = (
        _note_query(db)
        .join(latest_subq, NursingNote.id == latest_subq.c.max_id)
        .order_by(NursingNote.created_at.desc(), NursingNote.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    notes = _enrich_notes_batch(db, notes)
    return [_serialize_note(note, db) for note in notes]

def _occupied_bed_for_patient(db: Session, patient_id: int) -> Bed | None:
    return (
        db.query(Bed)
        .filter(
            Bed.patient_id == patient_id,
            Bed.status == "occupied",
        )
        .order_by(Bed.admitted_at.desc())
        .first()
    )


def _resolve_patient_and_appointment(
    db: Session,
    *,
    appointment_id: int | None,
    patient_id: int | None,
) -> tuple[Patient, Appointment | None]:
    appointment: Appointment | None = None

    if appointment_id is not None:
        appointment = (
            db.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if patient_id is not None and patient_id != appointment.patient_id:
            raise HTTPException(
                status_code=400,
                detail="patient_id does not match appointment",
            )
        patient = (
            db.query(Patient)
            .filter(Patient.id == appointment.patient_id)
            .first()
        )
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient, appointment

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active == True)  # noqa: E712
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not _occupied_bed_for_patient(db, patient.id):
        raise HTTPException(
            status_code=400,
            detail=(
                "patient_id is only allowed for patients currently occupying a bed, "
                "or provide appointment_id"
            ),
        )

    return patient, None


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    return f"{user.first_name} {user.last_name or ''}".strip()


def _patient_display_name(patient: Patient | None) -> str | None:
    if not patient:
        return None
    return f"{patient.first_name} {patient.last_name or ''}".strip()


def _status_value(status) -> str | None:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def _history_entry(note: NursingNote) -> dict:
    created_by = getattr(note, "created_by_name", None) or getattr(note, "nurse_name", None)
    return {
        "history_id": note.id,
        "created_at": note.created_at,
        "created_by": created_by,
        "status": _status_value(note.status) or "active",
        "symptoms": note.symptoms,
        "treatment_response": note.treatment_response,
        "additional_notes": note.additional_notes,
    }


def _patient_note_history(db: Session, patient_id: int) -> list[dict]:
    """All notes for a patient, newest first — powers Created At filter."""
    rows = (
        db.query(NursingNote)
        .filter(NursingNote.patient_id == patient_id)
        .order_by(NursingNote.created_at.desc(), NursingNote.id.desc())
        .all()
    )
    if not rows:
        return []

    nurse_ids = {n.nurse_id for n in rows if n.nurse_id}
    nurses = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(nurse_ids)).all()
    } if nurse_ids else {}

    history = []
    for row in rows:
        nurse = nurses.get(row.nurse_id)
        name = _user_display_name(nurse)
        row.nurse_name = name
        row.created_by_name = name
        history.append(_history_entry(row))
    return history


def _serialize_note(note: NursingNote, db: Session | None = None) -> NursingNoteResponse:
    patient = note.patient
    nurse = note.nurse if getattr(note, "nurse", None) is not None else None
    nurse_name = getattr(note, "nurse_name", None) or _user_display_name(nurse)
    history = _patient_note_history(db, note.patient_id) if db is not None else None
    payload = {
        "patient_uid": getattr(note, "patient_uid", None)
        or (patient.patient_uid if patient else None),
        "patient_name": getattr(note, "patient_name", None)
        or _patient_display_name(patient),
        "nurse_name": nurse_name,
        "created_by_name": getattr(note, "created_by_name", None) or nurse_name,
        "bed_number": getattr(note, "bed_number", None),
        "status": _status_value(note.status),
    }
    if history is not None:
        payload["history"] = history
    return NursingNoteResponse.model_validate(note).model_copy(update=payload)


def _note_query(db: Session):
    """Notes for active patients only (OPD soft-delete hides notes)."""
    return (
        db.query(NursingNote)
        .join(Patient, Patient.id == NursingNote.patient_id)
        .filter(Patient.is_active.is_(True))
        .options(
            joinedload(NursingNote.patient),
            joinedload(NursingNote.nurse),
        )
    )


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

    patient, appointment = _resolve_patient_and_appointment(
        db,
        appointment_id=note_data.appointment_id,
        patient_id=note_data.patient_id,
    )

    try:

        note = NursingNote(
            appointment_id=appointment.id if appointment else None,
            patient_id=patient.id,
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

        return _serialize_note(_enrich_note(db, note), db)

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
    """Overwrite the existing nursing note row in place (same id)."""

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

        allowed_fields = (
            "symptoms",
            "treatment_response",
            "additional_notes",
        )
        for field in allowed_fields:
            if field in update_data:
                setattr(note, field, update_data[field])

        now = datetime.now(IST)
        note.status = NursingNoteStatus.ACTIVE
        note.updated_by = nurse_id
        note.updated_at = now

        db.commit()
        db.refresh(note)
        note = (
            _note_query(db)
            .filter(NursingNote.id == note.id)
            .first()
        )

        return _serialize_note(_enrich_note(db, note), db)

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

    return _serialize_note(_enrich_note(db, note), db)


# ==========================================================
# GET ALL NOTES
# ==========================================================

def get_all_notes_service(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    allocated_only: bool = False,
    nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,
):

    query = _note_query(db)

    if allocated_only:
        from Services.nurse_shift_bed_allocation_service import (
            get_allocated_patient_ids_for_nurse,
        )

        patient_ids = get_allocated_patient_ids_for_nurse(
            db,
            nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        ) if nurse_id else []
        if not patient_ids:
            query = query.filter(NursingNote.patient_id == -1)
        else:
            query = query.filter(NursingNote.patient_id.in_(patient_ids))

    return _paginate_notes(
        db,
        query,
        page=page,
        page_size=page_size,
        latest_per_patient=True,
    )


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

    allocated_only: bool = False,
    allocation_nurse_id: int | None = None,
    assignment_date=None,
    shift_name: str | None = None,

    page: int = 1,
    page_size: int = 20
):

    query = _note_query(db)

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

    if allocated_only:
        from Services.nurse_shift_bed_allocation_service import (
            get_allocated_patient_ids_for_nurse,
        )

        patient_ids = get_allocated_patient_ids_for_nurse(
            db,
            allocation_nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        ) if allocation_nurse_id else []
        if not patient_ids:
            query = query.filter(NursingNote.patient_id == -1)
        else:
            query = query.filter(NursingNote.patient_id.in_(patient_ids))

    latest_per_patient = patient_id is None and appointment_id is None
    return _paginate_notes(
        db,
        query,
        page=page,
        page_size=page_size,
        latest_per_patient=latest_per_patient,
    )