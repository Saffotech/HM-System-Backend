from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.receptionist_schema import (
    DashboardResponse,
    DoctorQueueResponse,
    DoctorScheduleListResponse,
    QueueHistoryResponse,
    ReceptionistAppointmentStatus,
    TodayQueueResponse,
)
from Services import receptionist_service
from Services.queue_helpers import receptionist_payment_filter_from_query

router = APIRouter(prefix="/receptionist", tags=["Receptionist"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_dashboard(
    doctor_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    data = receptionist_service.get_dashboard(db, doctor_id=doctor_id)
    return {"success": True, "data": data}


@router.get(
    "/today-queue",
    response_model=TodayQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Today's checked-in patients (all doctors)",
)
def receptionist_today_queue(
    doctor_id: Optional[int] = Query(None, ge=1),
    doctor_name: Optional[str] = Query(None, min_length=1),
    patient_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[ReceptionistAppointmentStatus] = Query(
        None,
        alias="status",
        description="Filter by appointment status: scheduled or completed",
    ),
    payment_status: Optional[str] = Query(
        None,
        description="Filter by payment: paid or unpaid",
    ),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return {
        "success": True,
        **receptionist_service.get_today_queue(
            db,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            patient_id=patient_id,
            status=receptionist_service.receptionist_appointment_status_from_query(
                status_filter.value if status_filter else None
            ),
            payment_filter=receptionist_payment_filter_from_query(payment_status),
            search=search,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/doctor-queue/{doctor_id}",
    response_model=DoctorQueueResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_doctor_queue(
    doctor_id: int,
    status_filter: Optional[ReceptionistAppointmentStatus] = Query(
        None,
        alias="status",
        description="Filter by appointment status: scheduled or completed",
    ),
    payment_status: Optional[str] = Query(
        None,
        description="Filter by payment: paid or unpaid",
    ),
    search: Optional[str] = Query(None),
    queue_date: Optional[date] = Query(None, alias="date"),
    page: Optional[int] = Query(None, ge=1),
    limit: Optional[int] = Query(None, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return {
        "success": True,
        **receptionist_service.get_doctor_queue(
            db,
            doctor_id,
            status=receptionist_service.receptionist_appointment_status_from_query(
                status_filter.value if status_filter else None
            ),
            payment_filter=receptionist_payment_filter_from_query(payment_status),
            search=search,
            queue_date=queue_date,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/queue-history",
    response_model=QueueHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_queue_history(
    single_date: Optional[date] = Query(None, alias="date"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    doctor_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[ReceptionistAppointmentStatus] = Query(
        None,
        alias="status",
        description="Filter by appointment status: scheduled or completed",
    ),
    payment_status: Optional[str] = Query(
        None,
        description="Filter by payment: paid or unpaid",
    ),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return {
        "success": True,
        **receptionist_service.get_queue_history(
            db,
            single_date=single_date,
            date_from=date_from,
            date_to=date_to,
            doctor_id=doctor_id,
            status=receptionist_service.receptionist_appointment_status_from_query(
                status_filter.value if status_filter else None
            ),
            payment_filter=receptionist_payment_filter_from_query(payment_status),
            search=search,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/doctors/schedule",
    response_model=DoctorScheduleListResponse,
    status_code=status.HTTP_200_OK,
    summary="View doctor schedules and slot availability (read-only)",
)
def receptionist_doctor_schedule(
    schedule_date: date = Query(..., alias="date", description="Schedule date (required)"),
    doctor_id: Optional[int] = Query(None, ge=1),
    department_id: Optional[int] = Query(None, ge=1),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("receptionist:view_doctor_schedule")),
):
    return {
        "success": True,
        **receptionist_service.get_doctor_schedules(
            db,
            schedule_date=schedule_date,
            doctor_id=doctor_id,
            department_id=department_id,
            search=search,
            page=page,
            page_size=page_size,
        ),
    }
