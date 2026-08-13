from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from Schemas.common_schema import PaginatedResponse


# ==========================================================
# Today queue
# ==========================================================

class NurseDashboardQueueItem(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    patient_name: str
    patient_uid: str
    patient_phone: Optional[str] = None
    appointment_uid: Optional[str] = None
    doctor_id: int
    token_number: int
    queue_date: date
    status: str
    priority: str
    is_current: bool = False
    queue_entered_at: Optional[datetime] = None
    consultation_started_at: Optional[datetime] = None
    consultation_completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NurseDashboardQueueResponse(PaginatedResponse[NurseDashboardQueueItem]):
    pass


# ==========================================================
# Bed-assigned patients
# ==========================================================

class NurseDashboardBedPatientLastVitals(BaseModel):
    vital_id: int
    recorded_at: datetime
    temperature: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    status: Optional[str] = None


class NurseDashboardBedPatientItem(BaseModel):
    patient_id: int
    patient_name: str
    patient_uid: str
    patient_phone: Optional[str] = None
    bed_id: int
    bed_number: str
    ward_name: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    admitted_at: Optional[datetime] = None
    last_vitals: Optional[NurseDashboardBedPatientLastVitals] = None
    pending_medication_count: int = 0


class NurseDashboardBedPatientListResponse(PaginatedResponse[NurseDashboardBedPatientItem]):
    pass


# ==========================================================
# Nurse allocation summary (Phase 4 — additive endpoint)
# ==========================================================

class NurseBedAllocationSummaryResponse(BaseModel):
    success: bool = True
    has_allocations: bool = False
    assignment_date: date
    shift_name: Optional[str] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    assigned_bed_count: int = 0
    occupied_count: int = 0
    vacant_count: int = 0
    allocated_bed_ids: List[int] = Field(default_factory=list)


# ==========================================================
# Nurse self-service: My Duty (roster + allocated beds span)
# ==========================================================

class NurseMyDutyCurrentShift(BaseModel):
    shift_name: Optional[str] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None


class NurseMyDutyRosterPeriod(BaseModel):
    from_date: Optional[date] = None
    to_date: Optional[date] = None


class NurseMyDutyRosterItem(BaseModel):
    roster_date: date
    shift_name: Optional[str] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None


class NurseMyDutyBedItem(BaseModel):
    # Keep `id` for consistent table row-key usage on the frontend.
    id: int
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    assigned_from: date
    assigned_until: Optional[date] = None
    shift_name: Optional[str] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    department_name: Optional[str] = None
    is_occupied: bool = False


class NurseMyDutyResponse(BaseModel):
    success: bool = True
    current_shift: NurseMyDutyCurrentShift = NurseMyDutyCurrentShift()
    roster_period: NurseMyDutyRosterPeriod = NurseMyDutyRosterPeriod()
    my_beds: List[NurseMyDutyBedItem] = Field(default_factory=list)
    roster_items: List[NurseMyDutyRosterItem] = Field(default_factory=list)
