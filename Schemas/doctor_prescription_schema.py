from pydantic import BaseModel, field_validator, Field, model_validator, ConfigDict
from datetime import datetime
from typing import Optional, List

from Schemas.common_schema import PaginatedResponse
from Services.prescription_duration import normalize_duration

_normalize_duration = normalize_duration


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


class PrescriptionItemCreate(BaseModel):
    # Frontend may still send dose / quantity_unit; ignore so old clients keep working.
    model_config = ConfigDict(extra="ignore")

    medicine_name: str
    dosage: str
    frequency: str
    duration: str = Field(..., min_length=1, max_length=50)
    instructions: Optional[str] = None
    form: Optional[str] = Field(default=None, max_length=50)
    route: Optional[str] = Field(default=None, max_length=50)
    timing: Optional[str] = Field(default=None, max_length=50)
    quantity: Optional[int] = Field(default=None, ge=1)

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration_input(cls, v):
        return _normalize_duration(v)

    @field_validator(
        "form",
        "route",
        "timing",
        "instructions",
        mode="before",
    )
    @classmethod
    def coerce_optional_text(cls, v):
        return _blank_to_none(v)

    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_optional_quantity(cls, v):
        if v is None or v == "":
            return None
        return v


class PrescriptionCreate(BaseModel):

    appointment_id: Optional[int] = None
    admission_id: Optional[int] = None
    diagnosis: str
    notes: Optional[str] = None
    items: List[PrescriptionItemCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_one_parent(self):
        has_appointment = self.appointment_id is not None
        has_admission = self.admission_id is not None
        if has_appointment == has_admission:
            raise ValueError("Provide exactly one of appointment_id or admission_id")
        return self


class PrescriptionItemResponse(BaseModel):

    id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None
    form: Optional[str] = None
    route: Optional[str] = None
    timing: Optional[str] = None
    quantity: Optional[int] = None

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration_output(cls, v):
        return _normalize_duration(v)

    class Config:
        from_attributes = True


class PrescriptionResponse(BaseModel):

    id: int
    appointment_id: Optional[int] = None
    admission_id: Optional[int] = None
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
