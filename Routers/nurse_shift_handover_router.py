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

from Schemas.nurse_shift_handover_schema import (
    ShiftHandoverCreate,
    ShiftHandoverUpdate,
    ShiftHandoverPatientsBulkCreate,
    ShiftHandoverPatientUpdate
)

from Services.nurse_shift_handover_service import (
    create_handover_service,
    update_handover_service,
    bulk_add_handover_patients_service,
    update_handover_patient_service,
    delete_handover_patient_service,
    submit_handover_service,
    get_handover_list_service,
    get_handover_detail_service
)

router = APIRouter(
    prefix="/nurse/handover",
    tags=["Nurse Shift Handover"]
)


# ==========================================================
# CREATE HANDOVER
# ==========================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED
)
def create_handover(

    handover_data: ShiftHandoverCreate,

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:create"
        )
    ),

    db: Session = Depends(get_db)
):

    return create_handover_service(
        db=db,
        handover_data=handover_data,
        nurse_id=current_user.id
    )


# ==========================================================
# UPDATE HANDOVER
# ==========================================================

@router.put("/{handover_id}")
def update_handover(

    handover_data: ShiftHandoverUpdate,

    handover_id: int = Path(
        ...,
        ge=1,
        description="Handover ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:update"
        )
    ),

    db: Session = Depends(get_db)
):

    return update_handover_service(
        db=db,
        handover_id=handover_id,
        handover_data=handover_data,
        nurse_id=current_user.id
    )


# ==========================================================
# BULK ADD PATIENTS
# ==========================================================

@router.post(
    "/{handover_id}/patients/bulk",
    status_code=status.HTTP_201_CREATED
)
def add_handover_patients(

    patient_data: ShiftHandoverPatientsBulkCreate,

    handover_id: int = Path(
        ...,
        ge=1,
        description="Handover ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:create"
        )
    ),

    db: Session = Depends(get_db)
):

    return bulk_add_handover_patients_service(
        db=db,
        handover_id=handover_id,
        patient_data=patient_data,
        nurse_id=current_user.id
    )


# ==========================================================
# UPDATE PATIENT SUMMARY
# ==========================================================

@router.put("/patients/{patient_summary_id}")
def update_handover_patient(

    patient_data: ShiftHandoverPatientUpdate,

    patient_summary_id: int = Path(
        ...,
        ge=1,
        description="Patient Summary ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:update"
        )
    ),

    db: Session = Depends(get_db)
):

    return update_handover_patient_service(
        db=db,
        patient_summary_id=patient_summary_id,
        patient_data=patient_data,
        nurse_id=current_user.id
    )


# ==========================================================
# DELETE PATIENT SUMMARY
# ==========================================================

@router.delete("/patients/{patient_summary_id}")
def delete_handover_patient(

    patient_summary_id: int = Path(
        ...,
        ge=1,
        description="Patient Summary ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:update"
        )
    ),

    db: Session = Depends(get_db)
):

    return delete_handover_patient_service(
        db=db,
        patient_summary_id=patient_summary_id,
        nurse_id=current_user.id
    )


# ==========================================================
# SUBMIT HANDOVER
# ==========================================================

@router.put("/{handover_id}/submit")
def submit_handover(

    handover_id: int = Path(
        ...,
        ge=1,
        description="Handover ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:submit"
        )
    ),

    db: Session = Depends(get_db)
):

    return submit_handover_service(
        db=db,
        handover_id=handover_id,
        nurse_id=current_user.id
    )


# ==========================================================
# HANDOVER LIST
# ==========================================================

@router.get("")
def get_handovers(

    handover_uid: str | None = None,

    patient_id: int | None = Query(
        None,
        ge=1
    ),

    patient_uid: str | None = Query(
        None
    ),

    patient_name: str | None = None,

    status: str | None = None,

    ward_name: str | None = None,

    shift_date: date | None = None,

    outgoing_nurse_id: int | None = Query(
        None,
        ge=1
    ),

    page: int = Query(
        1,
        ge=1
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:view"
        )
    ),

    db: Session = Depends(get_db)
):

    return get_handover_list_service(
        db=db,

        handover_uid=handover_uid,

        patient_id=patient_id,

        patient_uid=patient_uid,

        patient_name=patient_name,

        status=status,

        ward_name=ward_name,

        shift_date=shift_date,

        outgoing_nurse_id=outgoing_nurse_id,

        page=page,

        page_size=page_size
    )


# ==========================================================
# HANDOVER DETAIL
# ==========================================================

@router.get("/{handover_id}")
def get_handover_detail(

    handover_id: int = Path(
        ...,
        ge=1,
        description="Handover ID"
    ),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_handover:view"
        )
    ),

    db: Session = Depends(get_db)
):

    return get_handover_detail_service(
        db=db,
        handover_id=handover_id
    )