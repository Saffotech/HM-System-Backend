from fastapi import (
    APIRouter,
    Depends,
    status
)

from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user,
    PermissionChecker
)

from Models.user import User

from Schemas.prescription_schema import (
    PrescriptionCreate,
    PrescriptionResponse
)

from Services.prescription_service import (

    create_prescription_service,

    get_prescription_by_id_service,

    get_patient_prescriptions_service,

    update_prescription_service,

    delete_prescription_service
)

router = APIRouter(
    prefix="/prescriptions",
    tags=["Prescriptions"]
)


# ==========================================================
# Create Prescription
# ==========================================================

@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_prescription(

    prescription_data: PrescriptionCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("prescriptions:create")
    )
):

    prescription = create_prescription_service(

        db=db,

        prescription_data=prescription_data,

        doctor_id=current_user.id
    )

    return prescription


# ==========================================================
# Get Prescription By ID
# ==========================================================

@router.get(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK
)
def get_prescription_by_id(

    prescription_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    prescription = get_prescription_by_id_service(

        db=db,

        prescription_id=prescription_id,

        doctor_id=current_user.id
    )

    return prescription


# ==========================================================
# Get Patient Prescription History
# ==========================================================

@router.get(
    "/patient/{patient_id}",
    response_model=list[PrescriptionResponse],
    status_code=status.HTTP_200_OK
)
def get_patient_prescriptions(

    patient_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    prescriptions = (
        get_patient_prescriptions_service(

            db=db,

            patient_id=patient_id,

            doctor_id=current_user.id
        )
    )

    return prescriptions


# ==========================================================
# Update Prescription
# ==========================================================

@router.put(
    "/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK
)
def update_prescription(

    prescription_id: int,

    prescription_data: PrescriptionCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("prescriptions:update")
    )
):

    prescription = update_prescription_service(

        db=db,

        prescription_id=prescription_id,

        prescription_data=prescription_data,

        doctor_id=current_user.id
    )

    return prescription


# ==========================================================
# Delete Prescription
# ==========================================================

@router.delete(
    "/{prescription_id}",
    status_code=status.HTTP_200_OK
)
def delete_prescription(

    prescription_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("prescriptions:delete")
    )
):

    result = delete_prescription_service(

        db=db,

        prescription_id=prescription_id,

        doctor_id=current_user.id
    )

    return result