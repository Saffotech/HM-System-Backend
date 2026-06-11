from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Path,
    status
)
from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user,
    PermissionChecker
)

from Models.user import User

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

    patient_id: int | None = Query(
        None,
        ge=1
    ),

    patient_name: str | None = None,

    patient_uid: str | None = None,

    bed_number: str | None = None,

    page: int = Query(
        1,
        ge=1
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_medication:view"
        )
    )
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

    patient_id: int = Path(
        ...,
        ge=1,
        description="Patient ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_medication:view"
        )
    )
):

    return get_patient_medications_service(
        db=db,
        patient_id=patient_id
    )


# ==========================================================
# ADMINISTER MEDICATION
# ==========================================================

@router.post(
    "/administer",
    status_code=status.HTTP_201_CREATED
)
def administer_medication(

    medication_data: MedicationAdministrationCreate,

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_medication:create"
        )
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

@router.put("/administer/{administration_id}")
def update_medication_administration(
    medication_data: MedicationAdministrationUpdate,
    administration_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("nurse_medication:update")
    ),
    db: Session = Depends(get_db)
):

    return update_medication_administration_service(
        db=db,
        administration_id=administration_id,
        medication_data=medication_data,
        nurse_id=current_user.id
    )


# ==========================================================
# MEDICATION HISTORY
# ==========================================================

@router.get("/history")
def get_medication_history(

    patient_id: int | None = Query(
        None,
        ge=1
    ),

    patient_name: str | None = None,

    patient_uid: str | None = None,

    bed_number: str | None = None,

    status: str | None = None,

    from_date: date | None = None,

    to_date: date | None = None,

    page: int = Query(
        1,
        ge=1
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_medication:view"
        )
    )
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

    patient_id: int = Path(
        ...,
        ge=1,
        description="Patient ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_medication:view"
        )
    )
):

    return get_patient_medication_history_service(
        db=db,
        patient_id=patient_id
    )