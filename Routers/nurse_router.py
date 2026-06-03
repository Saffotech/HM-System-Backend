from typing import List

from fastapi import (
    APIRouter,
    Depends
)

from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user,
)

from Models.user import User

from Schemas.nurse_schema import (
    VitalCreate,
    VitalResponse,
    NursingNoteCreate,
    NursingNoteResponse
)

from Services.nurse_service import (
    create_vital_service,
    get_patient_vitals_service,
    create_nursing_note_service,
    get_patient_notes_service
)

router = APIRouter(
    prefix="/nurse",
    tags=["Nurse"]
)

# ==========================================================
# CREATE VITALS
# ==========================================================

@router.post(
    "/vitals",
    response_model=VitalResponse
)
def create_vitals(
    vital_data: VitalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return create_vital_service(
        db=db,
        vital_data=vital_data,
        nurse_id=current_user.id
    )


# ==========================================================
# GET PATIENT VITALS HISTORY
# ==========================================================

@router.get(
    "/vitals/patient/{patient_id}",
    response_model=List[VitalResponse]
)
def get_patient_vitals(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return get_patient_vitals_service(
        db=db,
        patient_id=patient_id
    )


# ==========================================================
# CREATE NURSING NOTE
# ==========================================================

@router.post(
    "/notes",
    response_model=NursingNoteResponse
)
def create_nursing_note(
    note_data: NursingNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return create_nursing_note_service(
        db=db,
        note_data=note_data,
        nurse_id=current_user.id
    )


# ==========================================================
# GET PATIENT NOTES
# ==========================================================

@router.get(
    "/notes/patient/{patient_id}",
    response_model=List[NursingNoteResponse]
)
def get_patient_notes(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    return get_patient_notes_service(
        db=db,
        patient_id=patient_id
    )