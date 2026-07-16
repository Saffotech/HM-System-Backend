from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from Models.nurse_emergency_alert import (
    AlertType,
    AlertSeverity,
    AlertStatus,
)


class EmergencyAlertCreate(BaseModel):
    patient_id: int
    alert_type: AlertType
    severity: AlertSeverity
    title: Optional[str] = None
    description: Optional[str] = None


class EmergencyAlertAssign(BaseModel):
    assigned_nurse_id: Optional[int] = None


class EmergencyAlertResolve(BaseModel):
    resolution_notes: Optional[str] = None


class EmergencyAlertEscalate(BaseModel):
    doctor_id: Optional[int] = None
    escalation_notes: Optional[str] = None


class AlertTimelineItem(BaseModel):
    event: str
    timestamp: datetime


class EmergencyAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_uid: str
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    alert_type: AlertType
    severity: AlertSeverity
    title: Optional[str] = None
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None
    status: AlertStatus
    assigned_nurse_id: Optional[int] = None
    assigned_nurse_name: Optional[str] = None
    escalated: bool = False
    triggered_at: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmergencyAlertDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_uid: str
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    alert_type: AlertType
    severity: AlertSeverity
    title: Optional[str] = None
    description: Optional[str] = None
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None
    status: AlertStatus
    triggered_by: Optional[int] = None
    triggered_by_name: Optional[str] = None
    triggered_at: datetime
    assigned_nurse_id: Optional[int] = None
    assigned_nurse_name: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None
    escalated_to_doctor_id: Optional[int] = None
    escalated_doctor_name: Optional[str] = None
    escalation_notes: Optional[str] = None
    vital_id: Optional[int] = Field(default=None, gt=0)
    vital_exists: Optional[bool] = None
    medication_administration_id: Optional[int] = Field(default=None, gt=0)
    medication_exists: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    timeline: list[AlertTimelineItem] = []


class EmergencyAlertListResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List[EmergencyAlertResponse]


class EmergencyAlertSummaryResponse(BaseModel):
    active_total: int
    critical_count: int
    high_count: int
    medium_count: int
    unassigned_count: int


class EmergencyAlertCreateResponse(BaseModel):
    message: str
    alert_id: int
    alert_uid: str


class EmergencyAlertActionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    alert_id: Optional[int] = None


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
