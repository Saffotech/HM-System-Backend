"""Requests for the logged-in patient. No staff-only fields."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PatientBookAppointment(BaseModel):
    """Same facts the desk sends to POST /opd/appointments, minus patient_id.

    The patient id comes from the login, not from the body.
    """

    doctor_id: int
    department_id: int
    scheduled_at: datetime
    reason: Optional[str] = Field(None, max_length=500)


class PatientPayAppointment(BaseModel):
    """Pay the bill created for one of this patient's appointments."""

    payment_mode: str = "cash"
    paid_amount: float = Field(..., gt=0)
    transaction_reference: Optional[str] = None
