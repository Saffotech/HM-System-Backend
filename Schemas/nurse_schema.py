from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ==========================================================
# VITALS
# ==========================================================

class VitalCreate(BaseModel):

    appointment_id: int

    temperature: Optional[float] = None

    blood_pressure: Optional[str] = None

    heart_rate: Optional[int] = None

    respiratory_rate: Optional[int] = None

    oxygen_saturation: Optional[int] = None

    blood_sugar: Optional[float] = None

    weight: Optional[float] = None

    pain_level: Optional[int] = Field(default=None,)

    observation_notes: Optional[str] = None

    status: Optional[str] = "normal"


class VitalResponse(BaseModel):

    id: int

    appointment_id: int

    patient_id: int

    recorded_by: int

    temperature: Optional[float]

    blood_pressure: Optional[str]

    heart_rate: Optional[int]

    respiratory_rate: Optional[int]

    oxygen_saturation: Optional[int]

    blood_sugar: Optional[float]

    weight: Optional[float]

    pain_level: Optional[int]

    observation_notes: Optional[str]

    status: str

    recorded_at: datetime

    class Config:
        from_attributes = True


# ==========================================================
# NURSING NOTES
# ==========================================================

class NursingNoteCreate(BaseModel):

    appointment_id: int

    symptoms: Optional[str] = None

    treatment_response: Optional[str] = None

    additional_notes: Optional[str] = None

    status: Optional[str] = "active"


class NursingNoteResponse(BaseModel):

    id: int

    appointment_id: int

    patient_id: int

    nurse_id: int

    symptoms: Optional[str]

    treatment_response: Optional[str]

    additional_notes: Optional[str]

    status: str

    created_at: datetime

    class Config:
        from_attributes = True