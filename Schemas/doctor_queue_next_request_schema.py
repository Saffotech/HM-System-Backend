from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RequestNextPatientSchema(BaseModel):
    appointment_id: int


class SendInPatientSchema(BaseModel):
    appointment_id: int


class NextPatientRequestOut(BaseModel):
    id: int
    doctor_id: int
    doctor_name: Optional[str] = None
    appointment_id: int
    patient_id: int
    patient_name: Optional[str] = None
    patient_uid: Optional[str] = None
    appointment_time: Optional[str] = None
    status: str
    requested_at: datetime

    class Config:
        from_attributes = True
