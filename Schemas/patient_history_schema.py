from pydantic import BaseModel , Field
from datetime import date,datetime,time
from typing import Optional


# ==========================================================
# Patient Response Schema
# ==========================================================

class PatientResponse(BaseModel):

    patient_id: int

    patient_name: str

    patient_uhid: str

    doctor_id: int

    appointment_date: date

    appointment_time: time

    appointment_type: Optional[str]

    priority: Optional[str]

    status: str

    class Config:

        from_attributes = True

class PaginationSchema(BaseModel):

    page: int = Field(default=1,ge=1)
    limit: int = Field(default=10,ge=1,le=100)