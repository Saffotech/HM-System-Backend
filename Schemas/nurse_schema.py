from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, model_validator ,Field


# ==========================================================
#  CREATE VITALS
# ==========================================================

class VitalCreate(BaseModel):

    appointment_id: Optional[int] = None
    patient_id: Optional[int] = None

    temperature: Optional[float] = Field(None, ge=25, le=150)
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = Field(None, ge=1, le=300)
    respiratory_rate: Optional[int] = Field(None, ge=1, le=100)
    oxygen_saturation: Optional[int] = Field(None, ge=1, le=100)
    blood_sugar: Optional[float] = Field(None, gt=0, le=1000)
    weight: Optional[float] = Field(None, gt=0, le=500)
    pain_level: Optional[int] = Field(None, ge=0, le=10)

    observation_notes: Optional[str] = None

    @model_validator(mode="after")
    def require_appointment_or_patient(self):
        if self.appointment_id is None and self.patient_id is None:
            raise ValueError("Provide appointment_id or patient_id")
        return self

# ==========================================================
# UPDATE VITAL
# ==========================================================

class VitalUpdate(BaseModel):

    temperature: Optional[float] = Field(None, ge=25, le=45)
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = Field(None, ge=1, le=300)
    respiratory_rate: Optional[int] = Field(None, ge=1, le=100)
    oxygen_saturation: Optional[int] = Field(None, ge=1, le=100)
    blood_sugar: Optional[float] = Field(None, gt=0, le=1000)
    weight: Optional[float] = Field(None, gt=0, le=500)
    pain_level: Optional[int] = Field(None, ge=0, le=10)

    observation_notes: Optional[str] = None

# ==========================================================
# VITALS Response
# ==========================================================

class VitalResponse(BaseModel):

    id: int

    appointment_id: Optional[int] = None
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    recorded_by: int
    recorded_by_name: Optional[str] = None
    nurse_name: Optional[str] = None

    temperature: Optional[float]
    blood_pressure: Optional[str]
    heart_rate: Optional[int]
    respiratory_rate: Optional[int]
    oxygen_saturation: Optional[int]
    blood_sugar: Optional[float]
    weight: Optional[float]
    pain_level: Optional[int]
    observation_notes: Optional[str]

    status: Optional[str] = None
    recorded_at: datetime
    updated_at: Optional[datetime] = None
    # Newest-first list of all recordings for this patient (Recorded At filter)
    history: Optional[List[dict]] = None

    class Config:
        from_attributes = True


# ==========================================================
# CREATE NURSING NOTE
# ==========================================================

class NursingNoteCreate(BaseModel):

    appointment_id: Optional[int] = None
    patient_id: Optional[int] = None
    patient_id: Optional[int] = None

    symptoms: Optional[str] = None

    treatment_response: Optional[str] = None

    additional_notes: Optional[str] = None

    @model_validator(mode="after")
    def require_appointment_or_patient(self):
        if not self.appointment_id and not self.patient_id:
            raise ValueError("Provide appointment_id or patient_id")
        return self


# ==========================================================
# UPDATE NURSING NOTE
# ==========================================================

class NursingNoteUpdate(BaseModel):

    symptoms: Optional[str] = None

    treatment_response: Optional[str] = None

    additional_notes: Optional[str] = None


# ==========================================================
# RESPONSE
# ==========================================================

class NursingNoteResponse(BaseModel):

    id: int

    appointment_id: Optional[int] = None
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    nurse_id: int
    nurse_name: Optional[str] = None
    created_by_name: Optional[str] = None

    symptoms: Optional[str]
    treatment_response: Optional[str]
    additional_notes: Optional[str]

    status: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Newest-first list of all notes for this patient (Created At filter)
    history: Optional[List[dict]] = None

    class Config:
        from_attributes = True


# ==========================================================
#  Search Response
# ==========================================================

class SearchResponse(BaseModel):

    appointment_id: Optional[int] = None

    patient_id: int

    patient_uid: str

    first_name: str

    last_name: str | None = None

    phone: str

    status: str

    scheduled_at: Optional[datetime] = None

    class Config:
        from_attributes = True
