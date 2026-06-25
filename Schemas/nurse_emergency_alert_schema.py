from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel,ConfigDict
from Models.nurse_emergency_alert import (
    AlertType,
    AlertSeverity,
    AlertStatus
)

# ==========================================================
# CREATE ALERT
# ==========================================================

class EmergencyAlertCreate(BaseModel):

    patient_id: int
    alert_type: AlertType
    severity: AlertSeverity
    title: Optional[str] = None
    description: Optional[str] = None

# ==========================================================
# ASSIGN ALERT
# ==========================================================

class EmergencyAlertAssign(BaseModel):

    assigned_nurse_id: Optional[int] = None


# ==========================================================
# RESOLVE ALERT
# ==========================================================

class EmergencyAlertResolve(BaseModel):

    resolution_notes: Optional[str] = None


# ==========================================================
# ESCALATE ALERT
# ==========================================================

class EmergencyAlertEscalate(BaseModel):

    doctor_id: Optional[int] = None

    escalation_notes: Optional[str] = None


class AlertTimelineItem(BaseModel):
    event: str
    timestamp: datetime


# ==========================================================
# ALERT RESPONSE (LIST API)
# ==========================================================

class EmergencyAlertResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int

    alert_uid: str

    patient_id: int

    alert_type: AlertType

    severity: AlertSeverity

    title: Optional[str]

    ward_name: Optional[str]

    bed_number: Optional[str]

    status: AlertStatus

    assigned_nurse_id: Optional[int]

    assigned_nurse_name: Optional[str] = None

    escalated: bool

    triggered_at: datetime

    created_at: datetime

    updated_at: datetime


# ==========================================================
# ALERT DETAIL RESPONSE
# ==========================================================

class EmergencyAlertDetailResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    alert_uid: str

    patient_id: int

    patient_uid: Optional[str] = None

    patient_name: Optional[str] = None

    alert_type: AlertType

    severity: AlertSeverity

    title: Optional[str]

    description: Optional[str]

    ward_name: Optional[str]

    bed_number: Optional[str]

    status: AlertStatus

    triggered_by: Optional[int]

    triggered_by_name: Optional[str] = None

    triggered_at: datetime

    assigned_nurse_id: Optional[int]

    assigned_nurse_name: Optional[str] = None

    resolved_by: Optional[int]

    resolved_by_name: Optional[str] = None

    resolved_at: Optional[datetime]

    resolution_notes: Optional[str]

    escalated: bool

    escalated_at: Optional[datetime]

    escalated_to_doctor_id: Optional[int]

    escalated_doctor_name: Optional[str] = None

    escalation_notes: Optional[str]

    from pydantic import Field

    vital_id: Optional[int] = Field(
        default=None,
        gt=0
    )

    medication_administration_id: Optional[int] = Field(
        default=None,
        gt=0
    )

    created_at: datetime

    updated_at: datetime
    timeline: list[AlertTimelineItem] = []

# ==========================================================
# LIST RESPONSE
# ==========================================================

class EmergencyAlertListResponse(BaseModel):

    total: int

    page: int

    limit: int

    data: List[EmergencyAlertResponse]


# ==========================================================
# SUMMARY RESPONSE
# ==========================================================

class EmergencyAlertSummaryResponse(BaseModel):

    active_total: int

    critical_count: int

    high_count: int

    medium_count: int

    unassigned_count: int


# ==========================================================
# FILTERS
# ==========================================================

class EmergencyAlertFilters(BaseModel):

    status: Optional[AlertStatus] = None

    severity: Optional[AlertSeverity] = None

    alert_type: Optional[AlertType] = None

    ward_name: Optional[str] = None

    patient_id: Optional[int] = None

    assigned_nurse_id: Optional[int] = None

    search: Optional[str] = None

    from_date: Optional[date] = None

    to_date: Optional[date] = None

    page: int = 1

    limit: int = 20
