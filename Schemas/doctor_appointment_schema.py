from enum import Enum

from pydantic import BaseModel


class DoctorAppointmentStatusUpdate(str, Enum):
    """Doctor may complete or cancel. no_show = system."""

    completed = "completed"
    cancelled = "cancelled"


class AppointmentStatusUpdate(BaseModel):
    status: DoctorAppointmentStatusUpdate
