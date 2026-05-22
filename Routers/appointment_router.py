from datetime import date

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

from Schemas.appointment_schema import (
    AppointmentStatusUpdate
)

from Services.appointment_service import (

    get_today_appointments_service,

    get_appointment_by_id_service,

    update_appointment_status_service,

    get_appointment_history_service,

    get_appointments_by_date_service
)


# ==========================================================
# Router Configuration
# ==========================================================

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"]
)


# ==========================================================
# 1. Get Today's Appointments
# ==========================================================

@router.get(
    "/today",
    status_code=status.HTTP_200_OK
)
def get_today_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
    _: bool = Depends(
        PermissionChecker("appointments:view")
    )
):
    appointments = get_today_appointments_service(

        db=db,

        doctor_id=current_user.id
    )
    return {

        "success": True,

        "message": (
            "Today's appointments fetched successfully"
        ),

        "appointments": appointments
    }


@router.get(
    "/history",
    status_code=status.HTTP_200_OK
)
def get_appointment_history(

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("appointments:view")
    )
):

    appointments = get_appointment_history_service(

        db=db,

        doctor_id=current_user.id
    )

    return {

        "success": True,

        "message": (
            "Appointment history fetched successfully"
        ),

        "appointments": appointments
    }


# ==========================================================
# 3. Get Appointments By Date
# ==========================================================

@router.get(
    "/by-date/{appointment_date}",
    status_code=status.HTTP_200_OK
)
def get_appointments_by_date(

    appointment_date: date,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("appointments:view")
    )
):

    appointments = get_appointments_by_date_service(

        db=db,

        doctor_id=current_user.id,

        appointment_date=appointment_date
    )

    return {

        "success": True,

        "message": (
            "Appointments fetched successfully"
        ),

        "appointments": appointments
    }


# ==========================================================
# 4. Update Appointment Status
# ==========================================================

@router.put(
    "/{appointment_id}/status",
    status_code=status.HTTP_200_OK
)
def update_appointment_status(

    appointment_id: int,

    appointment_data: AppointmentStatusUpdate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("appointments:update")
    )
):

    appointment = update_appointment_status_service(

        db=db,

        appointment_id=appointment_id,

        doctor_id=current_user.id,

        status=appointment_data.status
    )

    return {

        "success": True,

        "message": (
            "Appointment status updated successfully"
        ),

        "appointment": appointment
    }


# ==========================================================
# 5. Get Appointment By ID
# IMPORTANT:
# ALWAYS KEEP DYNAMIC ROUTES LAST
# ==========================================================

@router.get(
    "/{appointment_id}",
    status_code=status.HTTP_200_OK
)
def get_appointment_by_id(

    appointment_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    _: bool = Depends(
        PermissionChecker("appointments:view")
    )
):

    appointment = get_appointment_by_id_service(

        db=db,

        appointment_id=appointment_id,

        doctor_id=current_user.id
    )

    return {

        "success": True,

        "appointment": appointment
    }