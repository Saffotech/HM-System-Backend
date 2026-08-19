from pydantic import BaseModel, field_validator, Field
from datetime import datetime
from typing import Optional, List

from Schemas.common_schema import PaginatedResponse
from Services.prescription_duration import normalize_duration

_normalize_duration = normalize_duration


class PrescriptionItemCreate(BaseModel):

    medicine_name: str
    dosage: str
    frequency: str
    duration: str = Field(..., min_length=1, max_length=50)
    instructions: Optional[str] = None

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration_input(cls, v):
        return _normalize_duration(v)


class PrescriptionCreate(BaseModel):

    appointment_id: int
    diagnosis: str
    notes: Optional[str] = None
    items: List[PrescriptionItemCreate]


class PrescriptionItemResponse(BaseModel):

    id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration_output(cls, v):
        return _normalize_duration(v)

    class Config:
        from_attributes = True


class PrescriptionResponse(BaseModel):

    id: int
    appointment_id: int
    patient_id: int
    patient_uid: Optional[str] = None
    doctor_id: int
    diagnosis: str
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    items: List[PrescriptionItemResponse]

    class Config:
        from_attributes = True


class PrescriptionListPaginatedResponse(PaginatedResponse[PrescriptionResponse]):
    pass
