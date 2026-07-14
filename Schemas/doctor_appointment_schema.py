from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DoctorAppointmentStatusUpdate(str, Enum):
    """Statuses doctors may set via API — no_show is system/DB only."""

    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class AppointmentStatusUpdate(BaseModel):
    status: DoctorAppointmentStatusUpdate


class AppointmentConsultationUpdate(BaseModel):
    """Clinical payload for PATCH /appointments/{id}/consultation (queue optional)."""

    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None

    class Config:
        json_schema_extra = {
            "example": {
                "symptoms": "Fever, cough",
                "diagnosis": "Viral URI",
                "notes": "Rest and fluids",
                "follow_up_date": "2026-07-15",
            }
        }


class AppointmentResponse(BaseModel):
    """Matches OPD appointments + joined patient fields."""

    id: int
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_uid: str
    doctor_id: int
    department_id: int
    scheduled_at: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_type: str
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


from Schemas.common_schema import PaginationParams


class PaginationSchema(PaginationParams):
    pass
