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
    NursingNoteCreate,
    NursingNoteUpdate,
    NursingNoteResponse
)

from Services.nurse_nursing_notes_service import (
    create_note_service,
    update_note_service,
    get_note_by_id_service,
    get_all_notes_service,
    search_notes_service
)

router = APIRouter(
    prefix="/nurse/notes",
    tags=["Nurse Notes"]
)


# ==========================================================
# CREATE NOTE
# ==========================================================

@router.post(
    "",
    response_model=NursingNoteResponse,
    status_code=status.HTTP_201_CREATED
)
def create_note(

    note_data: NursingNoteCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_notes:create"
        )
    )
):

    return create_note_service(
        db=db,
        note_data=note_data,
        nurse_id=current_user.id
    )


# ==========================================================
# UPDATE NOTE
# ==========================================================

@router.put(
    "/{note_id}",
    response_model=NursingNoteResponse
)
def update_note(

    note_data: NursingNoteUpdate,

    note_id: int = Path(
        ...,
        ge=1,
        description="Nursing Note ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_notes:update"
        )
    )
):

    return update_note_service(
        db=db,
        note_id=note_id,
        note_data=note_data,
        nurse_id=current_user.id,
    )


# ==========================================================
# SEARCH / FILTER NOTES
# ==========================================================

@router.get(
    "/search",
    response_model=List[NursingNoteResponse]
)
def search_notes(

    patient_id: int | None = Query(
        None,
        ge=1
    ),

    patient_uid: str | None = Query(
        None
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

    status: str | None = Query(
        None
    ),

    nurse_id: int | None = Query(
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
            "nurse_notes:view"
        )
    )
):

    return search_notes_service(
        db=db,

        patient_id=patient_id,
        patient_uid=patient_uid,
        appointment_id=appointment_id,

        name=name,
        phone=phone,

        status=status,
        nurse_id=nurse_id,

        from_date=from_date,
        to_date=to_date,

        page=page,
        page_size=page_size
    )


# ==========================================================
# GET ALL NOTES
# ==========================================================

@router.get(
    "",
    response_model=List[NursingNoteResponse]
)
def get_all_notes(

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
            "nurse_notes:view"
        )
    )
):

    return get_all_notes_service(
        db=db,
        page=page,
        page_size=page_size
    )


# ==========================================================
# GET SINGLE NOTE
# ==========================================================

@router.get(
    "/{note_id}",
    response_model=NursingNoteResponse
)
def get_note(

    note_id: int = Path(
        ...,
        ge=1,
        description="Nursing Note ID"
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker(
            "nurse_notes:view"
        )
    )
):

    return get_note_by_id_service(
        db=db,
        note_id=note_id
    )