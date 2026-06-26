from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from Models.opd_billing import AppointmentStatus


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


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
