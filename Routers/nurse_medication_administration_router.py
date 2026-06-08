from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from dependencies import get_current_user

from Schemas.nurse_medication_administration_schema import (
    MedicationAdministrationCreate,
    MedicationAdministrationUpdate
)

from Services.nurse_medication_administration_service import (
    get_medication_patients_service,
    get_patient_medications_service,
    administer_medication_service,
    update_medication_administration_service,
    get_patient_medication_history_service,
    get_medication_history_service
)

router = APIRouter(
    prefix="/nurse/medications",
    tags=["Nurse Medication Administration"]
)


# ==========================================================
# GET MEDICATION PATIENTS
# ==========================================================

@router.get("/patients")
def get_medication_patients(
    patient_id: int | None = None,
    patient_name: str | None = None,
    patient_uid: str | None = None,
    bed_number: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    return get_medication_patients_service(
        db=db,
        patient_id=patient_id,
        patient_name=patient_name,
        patient_uid=patient_uid,
        bed_number=bed_number,
        page=page,
        page_size=page_size
    )


# ==========================================================
# GET PATIENT MEDICATIONS
# ==========================================================

@router.get("/patient/{patient_id}")
def get_patient_medications(
    patient_id: int,
    db: Session = Depends(get_db)
):

    return get_patient_medications_service(
        db=db,
        patient_id=patient_id
    )


# ==========================================================
# ADMINISTER MEDICATION
# ==========================================================

@router.post("/administer")
def administer_medication(
    medication_data: MedicationAdministrationCreate,

    current_user=Depends(
        get_current_user
    ),

    db: Session = Depends(get_db)
):

    return administer_medication_service(
        db=db,
        medication_data=medication_data,
        nurse_id=current_user.id
    )


# ==========================================================
# UPDATE MEDICATION ADMINISTRATION
# ==========================================================

@router.put(
    "/administer/{administration_id}"
)
def update_medication_administration(
    administration_id: int,

    medication_data:MedicationAdministrationUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return update_medication_administration_service(
        db=db,
        administration_id=administration_id,
        medication_data=medication_data,
        nurse_id = current_user.id
    )

from datetime import date

@router.get("/history")
def get_medication_history(

    patient_id: int | None = None,

    patient_name: str | None = None,

    patient_uid: str | None = None,

    bed_number: str | None = None,

    status: str | None = None,

    from_date: date | None = None,

    to_date: date | None = None,

    page: int = 1,
    page_size: int = 20,

    db: Session = Depends(get_db)
):

    return get_medication_history_service(
        db=db,

        patient_id=patient_id,

        patient_name=patient_name,

        patient_uid=patient_uid,

        bed_number=bed_number,

        status=status,

        from_date=from_date,

        to_date=to_date,

        page=page,

        page_size=page_size
    )
# ==========================================================
# PATIENT MEDICATION HISTORY
# ==========================================================

@router.get("/history/{patient_id}")
def get_patient_medication_history(
    patient_id: int,

    db: Session = Depends(get_db)
):

    return get_patient_medication_history_service(
        db=db,
        patient_id=patient_id
    )