from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class VitalCreate(BaseModel):
    appointment_id: Optional[int] = None
    patient_id: Optional[int] = None
    temperature: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    blood_sugar: Optional[float] = None
    weight: Optional[float] = None
    pain_level: Optional[int] = None
    observation_notes: Optional[str] = None
    mark_critical: Optional[bool] = False

    @model_validator(mode="after")
    def require_appointment_or_patient(self):
        if not self.appointment_id and not self.patient_id:
            raise ValueError("Provide appointment_id or patient_id")
        return self


class VitalUpdate(BaseModel):
    temperature: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    blood_sugar: Optional[float] = None
    weight: Optional[float] = None
    pain_level: Optional[int] = None
    observation_notes: Optional[str] = None
    mark_critical: Optional[bool] = False
    status: Optional[str] = None


class VitalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: Optional[int] = None
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    bed_number: Optional[str] = None
    recorded_by: int
    recorded_by_name: Optional[str] = None
    temperature: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    blood_sugar: Optional[float] = None
    weight: Optional[float] = None
    pain_level: Optional[int] = None
    observation_notes: Optional[str] = None
    status: Optional[str] = None
    recorded_at: datetime


class NursingNoteCreate(BaseModel):
    appointment_id: Optional[int] = None
    patient_id: Optional[int] = None
    symptoms: Optional[str] = None
    treatment_response: Optional[str] = None
    additional_notes: Optional[str] = None

    @model_validator(mode="after")
    def require_appointment_or_patient(self):
        if not self.appointment_id and not self.patient_id:
            raise ValueError("Provide appointment_id or patient_id")
        return self


class NursingNoteUpdate(BaseModel):
    symptoms: Optional[str] = None
    treatment_response: Optional[str] = None
    additional_notes: Optional[str] = None
    status: Optional[str] = None


class NursingNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: Optional[int] = None
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    bed_number: Optional[str] = None
    nurse_id: int
    nurse_name: Optional[str] = None
    symptoms: Optional[str] = None
    treatment_response: Optional[str] = None
    additional_notes: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
