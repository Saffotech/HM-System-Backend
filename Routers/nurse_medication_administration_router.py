from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Path,
    Request,
    Response,
    status
)
from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user,
    PermissionChecker
)

from Models.user import User

from Services.audit_helpers import client_ip, user_agent
from Services import nurse_audit_service as nurse_audit
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
from Utils.pagination import set_pagination_headers

router = APIRouter(
    prefix="/nurse/medications",
    tags=["Nurse Medication Administration"]
)


# ==========================================================
# GET MEDICATION PATIENTS
# ==========================================================

@router.get("/patients")
def get_medication_patients(

    response: Response,

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

    allocated_only: bool = Query(
        False,
        description="If true, only medication patients on beds allocated to the current nurse.",
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

    result = get_medication_patients_service(
        db=db,
        patient_id=patient_id,
        patient_name=patient_name,
        patient_uid=patient_uid,
        bed_number=bed_number,
        allocated_only=allocated_only,
        nurse_id=current_user.id if allocated_only else None,
        page=page,
        page_size=page_size
    )
    set_pagination_headers(
        response,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
    return result["items"]


# ==========================================================
# GET PATIENT MEDICATIONS
# ==========================================================

@router.get("/patient/{patient_id}")
def get_patient_medications(

    request: Request,

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

    result = get_patient_medications_service(
        db=db,
        patient_id=patient_id
    )
    nurse_audit.log_medication_patient_view(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        patient_id=patient_id,
    )
    return result


# ==========================================================
# ADMINISTER MEDICATION
# ==========================================================

@router.post(
    "/administer",
    status_code=status.HTTP_201_CREATED
)
def administer_medication(

    medication_data: MedicationAdministrationCreate,
    request: Request,

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

    result = administer_medication_service(
        db=db,
        medication_data=medication_data,
        nurse_id=current_user.id
    )
    nurse_audit.log_medication_administer(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        result=result,
    )
    return result


# ==========================================================
# UPDATE MEDICATION ADMINISTRATION
# ==========================================================

@router.put("/administer/{administration_id}")
def update_medication_administration(
    medication_data: MedicationAdministrationUpdate,
    request: Request,
    administration_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        PermissionChecker("nurse_medication:update")
    ),
    db: Session = Depends(get_db)
):

    result = update_medication_administration_service(
        db=db,
        administration_id=administration_id,
        medication_data=medication_data,
        nurse_id=current_user.id
    )
    nurse_audit.log_medication_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        administration_id=administration_id,
        result=result,
    )
    return result


# ==========================================================
# MEDICATION HISTORY
# ==========================================================

@router.get("/history")
def get_medication_history(

    response: Response,

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

    result = get_medication_history_service(
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
    set_pagination_headers(
        response,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
    return result["items"]


# ==========================================================
# PATIENT MEDICATION HISTORY
# ==========================================================

@router.get("/history/{patient_id}")
def get_patient_medication_history(

    response: Response,

    patient_id: int = Path(
        ...,
        ge=1,
        description="Patient ID"
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
            "nurse_medication:view"
        )
    )
):

    result = get_patient_medication_history_service(
        db=db,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
    )
    set_pagination_headers(
        response,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
    return result["items"]