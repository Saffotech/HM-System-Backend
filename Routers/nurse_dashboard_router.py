from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Schemas.nurse_dashboard_schema import (
    NurseDashboardQueueResponse,
    NurseDashboardBedPatientListResponse,
    NurseDashboardBedPatientSummaryResponse,
    NurseDashboardStatsResponse,
    NursePatientOverviewResponse,
)
from Services.nurse_dashboard_service import (
    get_nurse_today_queue_service,
    get_nurse_bed_patients_service,
    get_nurse_bed_patients_summary_service,
    get_nurse_dashboard_stats_service,
)
from Services.nurse_patient_overview_service import (
    get_nurse_patient_overview_service,
)

router = APIRouter(
    prefix="/nurse",
    tags=["Nurse Dashboard"],
)


def _bed_patient_filters(
    search: str | None = Query(
        None,
        description="Search by patient name, UHID, phone, bed number, or ward",
    ),
    ward_name: str | None = Query(None, description="Filter by ward name"),
    bed_number: str | None = Query(None, description="Filter by bed number"),
    department_id: int | None = Query(None, ge=1, description="Filter by department"),
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
):
    return {
        "search": search,
        "ward_name": ward_name,
        "bed_number": bed_number,
        "department_id": department_id,
        "patient_id": patient_id,
        "patient_uid": patient_uid,
    }


@router.get("/dashboard/stats", response_model=NurseDashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return get_nurse_dashboard_stats_service(db)


@router.get("/queue/today", response_model=NurseDashboardQueueResponse)
def get_today_queue(
    search: str | None = Query(
        None,
        description="Search by name, UHID, phone, appointment UID, patient ID, or token",
    ),
    status: str | None = Query(
        None,
        description="waiting, vitals_completed, in_progress, completed, cancelled",
    ),
    doctor_id: int | None = Query(None, ge=1),
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
    priority: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return get_nurse_today_queue_service(
        db=db,
        search=search,
        status=status,
        doctor_id=doctor_id,
        patient_id=patient_id,
        patient_uid=patient_uid,
        priority=priority,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/beds/patients/summary",
    response_model=NurseDashboardBedPatientSummaryResponse,
)
def get_bed_assigned_patients_summary(
    filters: dict = Depends(_bed_patient_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return get_nurse_bed_patients_summary_service(db=db, **filters)


@router.get("/beds/patients", response_model=NurseDashboardBedPatientListResponse)
def get_bed_assigned_patients(
    filters: dict = Depends(_bed_patient_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return get_nurse_bed_patients_service(
        db=db,
        page=page,
        page_size=page_size,
        **filters,
    )


@router.get(
    "/patients/{patient_id}",
    response_model=NursePatientOverviewResponse,
)
def get_patient_overview(
    patient_id: int = Path(..., ge=1),
    notes_limit: int = Query(5, ge=1, le=50),
    alerts_limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("patients:view")),
):
    return get_nurse_patient_overview_service(
        db=db,
        patient_id=patient_id,
        notes_limit=notes_limit,
        alerts_limit=alerts_limit,
    )
