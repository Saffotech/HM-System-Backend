from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.doctor_patient_queue import QueueStatus
from Models.user import User
from Schemas.receptionist_schema import (
    ArrivalsResponse,
    CallPatientResponse,
    CheckInResponse,
    DashboardResponse,
    DoctorQueueResponse,
    PendingCallsResponse,
    QueueActionResponse,
    QueueHistoryResponse,
    TodayQueueResponse,
)
from Services import receptionist_service

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
    status_filter: Optional[QueueStatus] = Query(None, alias="status"),
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
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/arrivals",
    response_model=ArrivalsResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_arrivals(
    doctor_id: Optional[int] = Query(None, ge=1),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:view")),
):
    return {
        "success": True,
        **receptionist_service.get_arrivals(
            db,
            doctor_id=doctor_id,
            search=search,
            page=page,
            limit=limit,
        ),
    }

 
@router.post(
    "/check-in/{appointment_id}",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
)
def receptionist_check_in(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    queue = receptionist_service.check_in_patient(
        db, appointment_id, handled_by=current_user.id
    )
    return {
        "success": True,
        "message": "Patient checked in successfully",
        "queue": queue,
    }


@router.get(
    "/doctor-queue/{doctor_id}",
    response_model=DoctorQueueResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_doctor_queue(
    doctor_id: int,
    status_filter: Optional[QueueStatus] = Query(None, alias="status"),
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
            status=status_filter,
            search=search,
            queue_date=queue_date,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/pending-calls",
    response_model=PendingCallsResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_pending_calls(
    doctor_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return {
        "success": True,
        **receptionist_service.get_pending_calls(db, doctor_id=doctor_id),
    }


@router.post(
    "/call-patient/{queue_id}",
    response_model=CallPatientResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_call_patient(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    queue = receptionist_service.call_patient(db, queue_id, handled_by=current_user.id)
    return {
        "success": True,
        "message": "Patient called to doctor room",
        "queue": queue,
    }


@router.patch(
    "/queue/{queue_id}/no-show",
    response_model=QueueActionResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_no_show(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    queue = receptionist_service.mark_no_show(db, queue_id, handled_by=current_user.id)
    return {
        "success": True,
        "message": "Patient marked as no-show",
        "queue": queue,
    }


@router.patch(
    "/queue/{queue_id}/rejoin",
    response_model=QueueActionResponse,
    status_code=status.HTTP_200_OK,
)
def receptionist_rejoin(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("appointments:update")),
):
    queue = receptionist_service.rejoin_queue(db, queue_id, handled_by=current_user.id)
    return {
        "success": True,
        "message": "Patient rejoined the queue",
        "queue": queue,
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
    status_filter: Optional[QueueStatus] = Query(None, alias="status"),
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
            status=status_filter,
            search=search,
            page=page,
            limit=limit,
        ),
    }


@router.get(
    "/queue-history/export",
    status_code=status.HTTP_200_OK,
    summary="Export queue history as CSV (opens in Excel)",
)
def receptionist_queue_history_export(
    single_date: Optional[date] = Query(None, alias="date"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    doctor_id: Optional[int] = Query(None, ge=1),
    status_filter: Optional[QueueStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    export_format: Literal["csv"] = Query("csv", alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    content, filename = receptionist_service.export_queue_history_csv(
        db,
        single_date=single_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        status=status_filter,
        search=search,
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
