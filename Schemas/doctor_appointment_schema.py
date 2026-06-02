from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import Optional
from enum import Enum


# ==========================================================
# Appointment Status Enum
# ==========================================================

class AppointmentStatus(str, Enum):

    scheduled = "scheduled"
    waiting = "waiting"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


# ==========================================================
# Update Appointment Status Schema
# ==========================================================

class AppointmentStatusUpdate(BaseModel):

    status: AppointmentStatus


# ==========================================================
# Appointment Response Schema
# ==========================================================

class AppointmentResponse(BaseModel):

    id: int
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_age: Optional[int]
    patient_gender: Optional[str]
    patient_uhid: str
    doctor_id: int

    appointment_date: date
    appointment_time: time

    appointment_type: str
    priority: str
    status: str

    reason: Optional[str]
    notes: Optional[str]

    checked_in_at: Optional[datetime]
    consultation_started_at: Optional[datetime]
    consultation_completed_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==========================================================
# Pagination Schema
# ==========================================================

class PaginationSchema(BaseModel):

    page: int = Field(default=1,ge=1)
    limit: int = Field(default=10,ge=1,le=100)