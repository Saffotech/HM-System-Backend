from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional,List

class PrescriptionItemCreate(BaseModel):

    medicine_name: str
    dosage: str
    frequency: str
    duration: int
    instructions: Optional[str] = None

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration_input(cls, v):
        if isinstance(v, int):
            return v
        digits = "".join(c for c in str(v) if c.isdigit())
        return int(digits) if digits else 0

class PrescriptionCreate(BaseModel):

    appointment_id: int
    diagnosis: str
    notes: Optional[str] = None
    items: List[PrescriptionItemCreate]

class PrescriptionItemResponse(BaseModel):

    id : int
    medicine_name : str
    dosage : str
    frequency : str
    duration: int
    instructions: Optional[str] = None

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

