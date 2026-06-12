from datetime import date
from typing import List

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

from Schemas.nurse_schema import (
    VitalCreate,
    VitalUpdate,
    VitalResponse
)

from Services.nurse_patient_vitals_service import (
    create_vital_service,
    update_vital_service,
    get_vital_by_id_service,
    get_all_vitals_service,
    search_vitals_service
)

router = APIRouter(
    prefix="/nurse/vitals",
    tags=["Nurse Vitals"]
)


# ==========================================================
# CREATE VITAL
# ==========================================================

@router.post(
    "",
    response_model=VitalResponse,
    status_code=status.HTTP_201_CREATED
)
def create_vital(

    vital_data: VitalCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_vitals:create"
        )
    )
):

    return create_vital_service(
        db=db,
        vital_data=vital_data,
        nurse_id=current_user.id
    )


# ==========================================================
# UPDATE VITAL
# ==========================================================

@router.put(
    "/{vital_id}",
    response_model=VitalResponse
)
def update_vital(

    vital_data: VitalUpdate,

    vital_id: int = Path(
        ...,
        ge=1,
        description="Vital Record ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_vitals:update"
        )
    )
):

    return update_vital_service(
        db=db,
        vital_id=vital_id,
        vital_data=vital_data,
        nurse_id=current_user.id,
    )


# ==========================================================
# SEARCH / FILTER VITALS
# ==========================================================

@router.get(
    "/search",
    response_model=List[VitalResponse]
)
def search_vitals(

    patient_id: int | None = Query(
        None,
        ge=1
    ),

    appointment_id: int | None = Query(
        None,
        ge=1
    ),

    name: str | None = Query(
        None
    ),

    phone: str | None = Query(
        None
    ),

    uhid: str | None = Query(
        None
    ),

    status: str | None = Query(
        None
    ),

    recorded_by: int | None = Query(
        None,
        ge=1
    ),

    from_date: date | None = Query(
        None
    ),

    to_date: date | None = Query(
        None
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

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_vitals:view"
        )
    )
):

    return search_vitals_service(
        db=db,

        patient_id=patient_id,
        appointment_id=appointment_id,

        name=name,
        phone=phone,
        uhid=uhid,

        status=status,
        recorded_by=recorded_by,

        from_date=from_date,
        to_date=to_date,

        page=page,
        page_size=page_size
    )


# ==========================================================
# GET ALL VITALS
# ==========================================================

@router.get(
    "",
    response_model=List[VitalResponse]
)
def get_all_vitals(

    page: int = Query(
        1,
        ge=1,
        description="Page Number"
    ),

    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Records Per Page"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_vitals:view"
        )
    )
):

    return get_all_vitals_service(
        db=db,
        page=page,
        page_size=page_size
    )


# ==========================================================
# GET SINGLE VITAL
# ==========================================================

@router.get(
    "/{vital_id}",
    response_model=VitalResponse
)
def get_vital(

    vital_id: int = Path(
        ...,
        ge=1,
        description="Vital Record ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_vitals:view"
        )
    )
):

    return get_vital_by_id_service(
        db=db,
        vital_id=vital_id
    )