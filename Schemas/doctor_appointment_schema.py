from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DoctorAppointmentStatusUpdate(str, Enum):
    """Doctor may complete or cancel. no_show = system."""

    completed = "completed"
    cancelled = "cancelled"


class AppointmentStatusUpdate(BaseModel):
    status: DoctorAppointmentStatusUpdate


class AppointmentResponse(BaseModel):
    """Matches OPD appointments + joined patient fields."""

    id: int
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_age: Optional[int | str] = None
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


from Schemas.common_schema import PaginationParams, PaginatedResponse


class PaginationSchema(PaginationParams):
    pass


class AppointmentHistoryPaginatedResponse(PaginatedResponse[AppointmentResponse]):
    """Paginated completed appointment history for a doctor."""

    message: str = "Appointment history fetched successfully"
    # Legacy keys for existing doctor clients
    total_appointments: int = 0
    appointments: list[AppointmentResponse] = []
