from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_appointments import Appointment
from Models.nurse_patient_vitals import PatientVitals
from Models.nursing_notes import NursingNote

from Schemas.nurse_schema import (
    VitalCreate,
    NursingNoteCreate
)


# ==========================================================
# CREATE VITALS
# ==========================================================

def create_vital_service(
    db: Session,
    vital_data: VitalCreate,
    nurse_id: int
):

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == vital_data.appointment_id
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    if appointment.status not in [
        "scheduled",
        "checked_in"
    ]:
        raise HTTPException(
            status_code=400,
            detail="Vitals cannot be recorded for this appointment"
        )

    existing_vitals = (
        db.query(PatientVitals)
        .filter(
            PatientVitals.appointment_id == appointment.id
        )
        .first()
    )

    if existing_vitals:
        raise HTTPException(
            status_code=400,
            detail="Vitals already recorded for this appointment"
        )

    vital = PatientVitals(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        recorded_by=nurse_id,

        temperature=vital_data.temperature,
        blood_pressure=vital_data.blood_pressure,
        heart_rate=vital_data.heart_rate,
        respiratory_rate=vital_data.respiratory_rate,
        oxygen_saturation=vital_data.oxygen_saturation,
        blood_sugar=vital_data.blood_sugar,
        weight=vital_data.weight,
        pain_level=vital_data.pain_level,
        observation_notes=vital_data.observation_notes,
        status=vital_data.status
    )

    db.add(vital)
    db.commit()
    db.refresh(vital)

    return vital


# ==========================================================
# GET PATIENT VITALS HISTORY
# ==========================================================

def get_patient_vitals_service(
    db: Session,
    patient_id: int
):

    vitals = (
        db.query(PatientVitals)
        .filter(
            PatientVitals.patient_id == patient_id
        )
        .order_by(
            PatientVitals.recorded_at.desc()
        )
        .all()
    )

    return vitals


# ==========================================================
# GET APPOINTMENT VITALS
# ==========================================================

def get_appointment_vitals_service(
    db: Session,
    appointment_id: int
):

    vital = (
        db.query(PatientVitals)
        .filter(
            PatientVitals.appointment_id == appointment_id
        )
        .first()
    )

    if not vital:
        raise HTTPException(
            status_code=404,
            detail="Vitals not found"
        )

    return vital


# ==========================================================
# CREATE NURSING NOTE
# ==========================================================

def create_nursing_note_service(
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

    note = NursingNote(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        nurse_id=nurse_id,

        symptoms=note_data.symptoms,
        treatment_response=note_data.treatment_response,
        additional_notes=note_data.additional_notes,
        status=note_data.status
    )

    db.add(note)
    db.commit()
    db.refresh(note)

    return note


# ==========================================================
# GET PATIENT NOTES
# ==========================================================

def get_patient_notes_service(
    db: Session,
    patient_id: int
):

    notes = (
        db.query(NursingNote)
        .filter(
            NursingNote.patient_id == patient_id
        )
        .order_by(
            NursingNote.created_at.desc()
        )
        .all()
    )

    return notes


# ==========================================================
# GET APPOINTMENT NOTES
# ==========================================================

def get_appointment_notes_service(
    db: Session,
    appointment_id: int
):

    notes = (
        db.query(NursingNote)
        .filter(
            NursingNote.appointment_id == appointment_id
        )
        .order_by(
            NursingNote.created_at.desc()
        )
        .all()
    )

    return notes