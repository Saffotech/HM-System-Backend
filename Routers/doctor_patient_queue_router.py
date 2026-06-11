from fastapi import APIRouter,Depends,status
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user,PermissionChecker
from Models.user import User
from Schemas.doctor_patient_queue_schema import AddPatientQueueSchema
from Schemas.doctor_queue_next_request_schema import RequestNextPatientSchema
from Services.doctor_patient_queue_service import (

    add_patient_to_queue_service,
    get_today_queue_service,
    start_consultation_service,
    complete_consultation_service,
    get_current_consultation_service
)
from Services.doctor_queue_next_service import request_next_patient_service

router = APIRouter(
    prefix="/queue",
    tags=["Patient Queue"]
)


# ==========================================================
# Add Patient To Queue
# ==========================================================

@router.post("/add",
    status_code=status.HTTP_201_CREATED
)
def add_patient_to_queue(

    queue_data: AddPatientQueueSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update"))
):

    queue = add_patient_to_queue_service(
        db=db,
        appointment_id=queue_data.appointment_id
    )

    return {
        "success": True,
        "message": (
            "Patient added to queue successfully"
        ),
    "queue": queue
    }

# ==========================================================
# Get Today's Queue
# ==========================================================

@router.get("/today",
    status_code=status.HTTP_200_OK
)
def get_today_queue(

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):

    queue = get_today_queue_service(
        db=db,
        doctor_id=current_user.id
    )

    return {
        "success": True,
        "total_queue": len(queue),
        "queue": queue
    }

# ==========================================================
# Start Consultation
# ==========================================================

@router.put("/start/{queue_id}",
    status_code=status.HTTP_200_OK
)
def start_consultation(

    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update"))
):

    result = start_consultation_service(
        db=db,
        queue_id=queue_id,
        doctor_id=current_user.id
    )

    return {
        "success": True,
        "message": (
            "Consultation started successfully"
        ),
        "waiting_minutes": result[
            "waiting_minutes"
        ],
        "queue": result["queue"]
    }


# ==========================================================
# Complete Consultation
# ==========================================================

@router.put("/complete/{queue_id}",
    status_code=status.HTTP_200_OK
)
def complete_consultation(

    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update"))
):

    result = complete_consultation_service(

        db=db,
        queue_id=queue_id,
        doctor_id=current_user.id
    )

    return {
        "success": True,
        "message": (
            "Consultation completed successfully"
        ),
        "consultation_minutes": result[
            "consultation_minutes"
        ],
        "queue": result["queue"]
    }

# ==========================================================
# Get Current Consultation
# ==========================================================

@router.get("/current",
    status_code=status.HTTP_200_OK
)
def get_current_consultation(

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view"))
):

    queue = get_current_consultation_service(
        db=db,
        doctor_id=current_user.id
    )

    return {
        "success": True,
        "queue": queue
    }


# ==========================================================
# Request Next Patient (notify receptionist)
# ==========================================================

@router.post(
    "/request-next",
    status_code=status.HTTP_201_CREATED,
)
def request_next_patient(
    body: RequestNextPatientSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    request_row = request_next_patient_service(
        db=db,
        doctor_id=current_user.id,
        appointment_id=body.appointment_id,
    )
    return {
        "success": True,
        "message": "Next patient request sent to reception",
        "request": request_row,
    }