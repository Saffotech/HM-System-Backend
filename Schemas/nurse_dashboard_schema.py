from datetime import date, datetime
from typing import Any, Dict, List, Optional

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


class NurseDashboardBedPatientSummaryResponse(BaseModel):
    success: bool = True
    occupied_count: int


# ==========================================================
# Dashboard stats
# ==========================================================

class NurseDashboardQueueStats(BaseModel):
    total: int = 0
    waiting: int = 0
    vitals_completed: int = 0
    completed: int = 0
    cancelled: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)


class NurseDashboardBedsStats(BaseModel):
    occupied_count: int = 0


class NurseDashboardAlertsStats(BaseModel):
    active_count: int = 0
    critical_count: int = 0
    high_count: int = 0


class NurseDashboardHandoversStats(BaseModel):
    submitted_count: int = 0
    awaiting_take_over_count: int = 0


class NurseDashboardMedicationsStats(BaseModel):
    pending_count_occupied_beds: int = 0


class NurseDashboardStatsResponse(BaseModel):
    success: bool = True
    queue_today: NurseDashboardQueueStats
    beds: NurseDashboardBedsStats
    alerts: NurseDashboardAlertsStats
    handovers: NurseDashboardHandoversStats
    medications: NurseDashboardMedicationsStats


# ==========================================================
# Patient overview
# ==========================================================

class NursePatientOverviewPatient(BaseModel):
    id: int
    patient_uid: str
    first_name: str
    last_name: Optional[str] = None
    full_name: str
    phone: Optional[str] = None
    gender: Optional[Any] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None


class NursePatientOverviewBed(BaseModel):
    bed_id: int
    bed_number: str
    ward_name: Optional[str] = None
    department_id: Optional[int] = None
    admitted_at: Optional[datetime] = None


class NursePatientOverviewNote(BaseModel):
    id: int
    symptoms: Optional[str] = None
    treatment_response: Optional[str] = None
    additional_notes: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class NursePatientOverviewAlert(BaseModel):
    alert_id: int
    alert_uid: str
    alert_type: str
    severity: str
    title: Optional[str] = None
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None
    triggered_at: Optional[datetime] = None
    assigned_nurse_id: Optional[int] = None


class NursePatientOverviewMedication(BaseModel):
    prescription_item_id: int
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    instructions: Optional[str] = None
    is_given: bool = False


class NursePatientOverviewResponse(BaseModel):
    success: bool = True
    patient: NursePatientOverviewPatient
    bed: Optional[NursePatientOverviewBed] = None
    last_vitals: Optional[NurseDashboardBedPatientLastVitals] = None
    pending_medication_count: int = 0
    medications: List[NursePatientOverviewMedication] = Field(default_factory=list)
    recent_notes: List[NursePatientOverviewNote] = Field(default_factory=list)
    active_alerts: List[NursePatientOverviewAlert] = Field(default_factory=list)
