from datetime import datetime, date, time

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.patient import Patient
from Models.opd_billing import Bed
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.nurse_medication_administration import MedicationAdministration
from Schemas.nurse_medication_administration_schema import (
    MedicationAdministrationCreate,
    MedicationAdministrationUpdate,
    MedicationAdministrationResponse,
)
from Services import nurse_helpers as nh
from Services.nurse_emergency_alert_triggers import (
    process_medication_missed_alert,
)

def _serialize_administration(
    administration: MedicationAdministration,
) -> MedicationAdministrationResponse:
    return MedicationAdministrationResponse.model_validate(
        administration
    ).model_copy(
        update={
            "patient_uid": (
                administration.patient.patient_uid
                if administration.patient else None
            )
        }
    )


def _administration_query(db: Session):
    return db.query(MedicationAdministration).options(
        joinedload(MedicationAdministration.patient)
    )


def get_medication_patients_service(
    db: Session,

    patient_id: int | None = None,
    patient_name: str | None = None,
    patient_uid: str | None = None,
    bed_number: str | None = None,

    page: int = 1,
    page_size: int = 20
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100"
        )

    query = (
        db.query(Prescription, Patient, Bed)
        .join(Patient, Patient.id == Prescription.patient_id)
        .join(Bed, Bed.patient_id == Patient.id)
        .filter(
            Bed.status == "occupied",
            Patient.is_active.is_(True),
        )
    )

    # ======================================================
    # FILTERS
    # ======================================================

    if patient_id:
        query = query.filter(
            Patient.id == patient_id
        )

    if patient_name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{patient_name}%"
                ),
                Patient.last_name.ilike(
                    f"%{patient_name}%"
                )
            )
        )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if bed_number:
        query = query.filter(
            Bed.bed_number.ilike(
                f"%{bed_number}%"
            )
        )

    # ======================================================
    # PAGINATION
    # ======================================================

    records = (
        query
        .order_by(
            Prescription.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    result = []

    for prescription, patient, bed in records:

        medicine_count = (
            db.query(PrescriptionItem)
            .filter(
                PrescriptionItem.prescription_id
                == prescription.id
            )
            .count()
        )
 
        result.append({
            "patient_id": patient.id,
            "patient_name": nh.patient_display_name(patient) or "",
            "patient_uid": patient.patient_uid,
            "bed_number": bed.bed_number,
            "ward_name": bed.ward_name,
            "medicine_count": medicine_count,
        })

    return result


def get_patient_medications_service(
    db: Session,
    patient_id: int
):

    patient = (db.query(Patient)
        .filter(Patient.id == patient_id,Patient.is_active == True)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    prescription = (
        db.query(Prescription)
        .filter(
            Prescription.patient_id == patient_id
        )
        .order_by(Prescription.created_at.desc())
        .first()
    )

    if not prescription:
        raise HTTPException(
            status_code=404,
            detail="Prescription not found"
        )

    medications = (
        db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.prescription_id
            == prescription.id
        )
        .all()
    )

    bed = nh.occupied_bed_for_patient(db, patient_id)
    return {
        "patient_id": patient.id,
        "patient_uid": patient.patient_uid,
        "patient_name": nh.patient_display_name(patient) or "",
        "bed_number": bed.bed_number if bed else None,
        "ward_name": bed.ward_name if bed else None,
        "medications": [
            {
                "prescription_item_id": item.id,
                "medicine_name": item.medicine_name,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
                "instructions": item.instructions,
            }
            for item in medications
        ],
    }

def administer_medication_service(
    db: Session,
    medication_data:
    MedicationAdministrationCreate,
    nurse_id: int
):

    item = (db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.id ==
            medication_data.prescription_item_id
        ).first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Prescription item not found"
        )

    prescription = (
    db.query(Prescription)
    .filter(
        Prescription.id ==
        item.prescription_id
    )
    .first()
    )

    if not prescription:
        raise HTTPException(
            status_code=404,
            detail="Prescription not found"
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == prescription.patient_id,
            Patient.is_active == True
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found or inactive"
        )

    bed = nh.occupied_bed_for_patient(db, prescription.patient_id)

    administration = MedicationAdministration(
        prescription_item_id=item.id,
        patient_id=prescription.patient_id,
        administered_by=nurse_id,

        medicine_name=item.medicine_name,
        dosage=item.dosage,
        frequency=item.frequency,

        scheduled_time=medication_data.scheduled_time,

        bed_number=bed.bed_number if bed else None,
        ward_name=bed.ward_name if bed else None,

        status=medication_data.status,
        remarks=medication_data.remarks,

        is_active=True,
        created_by=nurse_id,
        updated_by=nurse_id
    )

    try:
        db.add(administration)
        db.commit()
        db.refresh(administration)
        administration = (
            _administration_query(db)
            .filter(
                MedicationAdministration.id == administration.id
            )
            .first()
        )

        process_medication_missed_alert(
            db=db,
            administration=administration,
            nurse_id=nurse_id,
        )

    except Exception:
        db.rollback()
        raise

    return _serialize_administration(administration)


def update_medication_administration_service(
    db: Session,
    administration_id: int,
    medication_data: MedicationAdministrationUpdate,
    nurse_id: int
):

    administration = (
        db.query(
            MedicationAdministration
        )
        .filter(
            MedicationAdministration.id == administration_id,
            MedicationAdministration.is_active == True
        )
        .first()
    )

    if not administration:
        raise HTTPException(
            status_code=404,
            detail=
            "Medication record not found"
        )

    update_data = (
        medication_data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in (
        update_data.items()
    ):
        setattr(
            administration,
            field,
            value
        )

    administration.updated_by = nurse_id

    try:
        db.add(administration)
        db.commit()
        db.refresh(administration)
        administration = (
            _administration_query(db)
            .filter(
                MedicationAdministration.id == administration.id
            )
            .first()
        )

        process_medication_missed_alert(
            db=db,
            administration=administration,
            nurse_id=nurse_id,
        )

    except Exception:
        db.rollback()
        raise

    return _serialize_administration(administration)

def get_patient_medication_history_service(
    db: Session,
    patient_id: int,
    page: int = 1,
    page_size: int = 20
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100"
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.id == patient_id,
            Patient.is_active == True
        )
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found"
        )

    history = (
        _administration_query(db)
        .filter(
            MedicationAdministration.patient_id == patient_id,
            MedicationAdministration.is_active == True
        )
        .order_by(
            MedicationAdministration.administered_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return [
        _serialize_administration(record)
        for record in history
    ]


def get_medication_history_service(
    db: Session,

    patient_id: int | None = None,

    patient_name: str | None = None,

    patient_uid: str | None = None,

    bed_number: str | None = None,

    status: str | None = None,

    from_date: date | None = None,

    to_date: date | None = None,

    page: int = 1,
    page_size: int = 20
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100"
        )
    # get_medication_history_service()

    query = (
        _administration_query(db)
        .join(
            Patient,
            Patient.id == MedicationAdministration.patient_id
        )
        .filter(
            MedicationAdministration.is_active == True
        )
    )

    if patient_id:
        query = query.filter(
            MedicationAdministration.patient_id
            == patient_id
        )

    if patient_name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{patient_name}%"
                ),
                Patient.last_name.ilike(
                    f"%{patient_name}%"
                )
            )
          )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if bed_number:
        query = query.filter(
            MedicationAdministration.bed_number.ilike(
                f"%{bed_number}%"
            )
        )

    if status:
        query = query.filter(
            MedicationAdministration.status
            == status
        )

    if from_date:
        query = query.filter(
            MedicationAdministration.administered_at
            >= from_date
        )


    if to_date:
        query = query.filter(
            MedicationAdministration.administered_at <=
            datetime.combine(
                to_date,
                time.max
            )
        )

    records = (
        query
        .order_by(
            MedicationAdministration
            .administered_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return [
        _serialize_administration(record)
        for record in records
    ]