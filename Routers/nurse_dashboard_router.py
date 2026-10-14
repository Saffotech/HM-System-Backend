from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, PermissionChecker
from Models.user import User
from Schemas.nurse_dashboard_schema import (
    NurseDashboardQueueResponse,
    NurseDashboardBedPatientListResponse,
    NurseBedAllocationSummaryResponse,
    NurseMyDutyResponse,)
from Services.nurse_dashboard_service import (
    get_nurse_today_queue_service,
    get_nurse_bed_patients_service,
    get_nurse_my_duty_service,)
from Services.nurse_shift_bed_allocation_service import (
    get_nurse_allocation_summary_service,
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
    allocated_only: bool = Query(
        False,
        description=(
            "If true, only patients on beds allocated to the current nurse "
            "for the assignment date/shift. Default false = hospital-wide (unchanged)."
        ),
    ),
    assignment_date: date | None = Query(
        None,
        description="Optional assignment date for allocated_only (defaults to today IST)",
    ),
    shift_name: str | None = Query(
        None,
        description="Optional shift name for allocated_only (defaults to current shift window)",
    ),
):
    return {
        "search": search,
        "ward_name": ward_name,
        "bed_number": bed_number,
        "department_id": department_id,
        "patient_id": patient_id,
        "patient_uid": patient_uid,
        "allocated_only": allocated_only,
        "assignment_date": assignment_date,
        "shift_name": shift_name,
    }


@router.get("/queue/today", response_model=NurseDashboardQueueResponse)
def get_today_queue(
    search: str | None = Query(
        None,
        description="Search by name, UHID, phone, appointment UID, patient ID, or token",
    ),
    status: str | None = Query(
        None,
        description="scheduled, completed, cancelled",
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
    "/beds/allocation-summary",
    response_model=NurseBedAllocationSummaryResponse,
)
def get_bed_allocation_summary(
    assignment_date: date | None = Query(None),
    shift_name: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    """Additive Phase 4 summary — uses existing opd:view permission."""
    return get_nurse_allocation_summary_service(
        db,
        current_user.id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )


@router.get("/beds/patients", response_model=NurseDashboardBedPatientListResponse)
def get_bed_assigned_patients(
    filters: dict = Depends(_bed_patient_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    allocated_only = bool(filters.pop("allocated_only", False))
    assignment_date = filters.pop("assignment_date", None)
    shift_name = filters.pop("shift_name", None)
    return get_nurse_bed_patients_service(
        db=db,
        page=page,
        page_size=page_size,
        allocated_only=allocated_only,
        nurse_id=current_user.id if allocated_only else None,
        assignment_date=assignment_date,
        shift_name=shift_name,
        **filters,
    )


@router.get("/my-duty", response_model=NurseMyDutyResponse)
def get_my_duty(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd:view")),
):
    return get_nurse_my_duty_service(db=db, nurse_id=current_user.id)
