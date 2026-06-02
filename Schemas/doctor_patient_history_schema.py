from typing import Optional

from pydantic import BaseModel, Field


class PatientHistoryItem(BaseModel):
    """Completed visit row for doctor patient history (OPD appointment + patient)."""

    id: int
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_uhid: str
    patient_phone: str
    doctor_id: int
    department_id: int
    scheduled_at: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_type: str
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class PaginationSchema(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)
