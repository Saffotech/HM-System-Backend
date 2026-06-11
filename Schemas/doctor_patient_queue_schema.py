from pydantic import BaseModel
from datetime import datetime,date
from typing import Optional

class AddPatientQueueSchema(BaseModel):
    appointment_id: int


class QueueStatusUpdateSchema(BaseModel):
    status: str


class PatientQueueSchema(BaseModel):
    id : int

    appointment_id : int
    patient_uuid : str
    patient_id : int
    patient_name : str
    patient_phone: str | None = None
    appointment_uid: str | None = None
    doctor_id : int
    token_number : int

    queue_date : date

    status: str
    priority : str

    queue_entered_at : datetime

    consultation_started_at: Optional[datetime]
    consultation_completed_at: Optional[datetime]

    created_at: datetime

    class Config:
        from_attributes = True

