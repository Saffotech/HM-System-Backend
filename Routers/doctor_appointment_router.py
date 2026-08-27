from datetime import date
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session
from database import get_db
from dependencies import (
    get_current_user,
    PermissionChecker,
)
from Models.user import User
from Schemas.doctor_appointment_schema import (
    AppointmentStatusUpdate,
)

from Services.audit_helpers import client_ip, user_agent
from Services import doctor_audit_service as doctor_audit
from Services.doctor_appointment_service import (
    get_today_appointments_service,
    get_appointment_by_id_service,
    update_appointment_status_service,
    get_appointment_history_service,
    get_appointments_by_date_service,
)
from Utils.pagination import paginate_sequence

router = APIRouter(
    prefix="/appointments",
    tags=["Doctor Appointments"],
)


# ==========================================================
# Get Today's Appointments
# ==========================================================

@router.get(
    "/today",
    status_code=status.HTTP_200_OK,
)
def get_today_appointments(
    page: int | None = Query(
        None,
        ge=1,
        description="Optional page. Omit to return the full list (legacy clients).",
    ),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description="Optional page size when page is provided.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    appointments = get_today_appointments_service(
        db=db,
        doctor_id=current_user.id,
    )
    items, total, page_n, size = paginate_sequence(
        appointments, page=page, page_size=page_size
    )
    payload = {
        "success": True,
        "message": "Today's appointments fetched successfully",
        "appointment": total,
        "appointments": items,
    }
    if page is not None:
        payload["page"] = page_n
        payload["page_size"] = size
        payload["total"] = total
    return payload


# ==========================================================
# Appointment History
# ==========================================================

@router.get(
    "/history",
    status_code=status.HTTP_200_OK,
)
def get_appointment_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return get_appointment_history_service(
        db=db,
        doctor_id=current_user.id,
        page=page,
        page_size=page_size,
    )


# ==========================================================
# Get Appointments By Date
# ==========================================================

@router.get(
    "/by-date/{appointment_date}",
    status_code=status.HTTP_200_OK,
)
def get_appointments_by_date(
    appointment_date: date,
    page: int | None = Query(
        None,
        ge=1,
        description="Optional page. Omit to return the full list (legacy clients).",
    ),
    page_size: int | None = Query(
        None,
        ge=1,
        le=100,
        description="Optional page size when page is provided.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    appointments = get_appointments_by_date_service(
        db=db,
        doctor_id=current_user.id,
        appointment_date=appointment_date,
    )
    items, total, page_n, size = paginate_sequence(
        appointments, page=page, page_size=page_size
    )
    payload = {
        "success": True,
        "message": "Appointments fetched successfully",
        "total_appointments": total,
        "appointments": items,
    }
    if page is not None:
        payload["page"] = page_n
        payload["page_size"] = size
        payload["total"] = total
    return payload


# ==========================================================
# Update Appointment Status
# ==========================================================

@router.put(
    "/{appointment_id}/status",
    status_code=status.HTTP_200_OK,
)
def update_appointment_status(
    appointment_id: int,
    appointment_data: AppointmentStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    appointment, previous_status = update_appointment_status_service(
        db=db,
        appointment_id=appointment_id,
        doctor_id=current_user.id,
        status=appointment_data.status,
    )
    new_status = getattr(appointment_data.status, "value", appointment_data.status)
    doctor_audit.log_appointment_status_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        appointment_id=appointment_id,
        new_status=str(new_status),
        previous_status=previous_status,
    )

    return {
        "success": True,
        "message": "Appointment status updated successfully",
        "appointment": appointment,
    }


# ==========================================================
# Get Appointment By ID
# ==========================================================

@router.get(
    "/{appointment_id}",
    status_code=status.HTTP_200_OK,
)
def get_appointment_by_id(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    appointment = get_appointment_by_id_service(
        db=db,
        appointment_id=appointment_id,
        doctor_id=current_user.id,
    )

    return {
        "success": True,
        "appointment": appointment,
    }
