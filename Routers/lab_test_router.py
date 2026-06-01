from fastapi import (
    APIRouter,
    Depends,
    status
)

from sqlalchemy.orm import Session

from database import get_db

from Models.user import User

from Schemas.lab_test_schema import (
    LabTestCreate,
    LabTestUpdate,
    LabTestResponse,
    LabTestListResponse
)

from Services.lab_test_service import (
    create_lab_test_service,
    get_lab_tests_service,
    update_lab_test_service,
    cancel_lab_test_service
)

from dependencies import get_current_user


router = APIRouter(
    prefix="/lab-tests",
    tags=["Lab Tests"]
)


# ==========================================================
# Create Lab Test
# ==========================================================

@router.post(
    "",
    response_model=LabTestResponse,
    status_code=status.HTTP_201_CREATED
)
def create_lab_test(
    payload: LabTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return create_lab_test_service(
        db=db,
        payload=payload,
        doctor_id=current_user.id
    )


# ==========================================================
# View All / Search Lab Tests
# ==========================================================

@router.get(
    "",
    response_model=list[LabTestListResponse]
)
def get_lab_tests(
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_lab_tests_service(
        db=db,
        doctor_id=current_user.id,
        search=search,
        skip=skip,
        limit=limit
    )


# ==========================================================
# Update Lab Test
# ==========================================================

@router.put(
    "/{test_id}",
    response_model=LabTestResponse
)
def update_lab_test(
    test_id: int,
    payload: LabTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return update_lab_test_service(
        db=db,
        test_id=test_id,
        payload=payload,
        doctor_id=current_user.id
    )


# ==========================================================
# Cancel Lab Test
# ==========================================================

@router.patch(
    "/{test_id}/cancel"
)
def cancel_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return cancel_lab_test_service(
        db=db,
        test_id=test_id,
        doctor_id=current_user.id
    )