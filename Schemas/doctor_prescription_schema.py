from pydantic import BaseModel, field_validator, Field
from datetime import datetime
from typing import Optional, List
import re

from Schemas.common_schema import PaginatedResponse


_DURATION_UNIT_RE = re.compile(
    r"(?i)\b(days?|weeks?|months?|years?)\b"
)


def _normalize_duration(value) -> str:
    """
    Keep full duration text when unit is present.
    If only a number is sent/stored (current doctor FE), default unit to days.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        return f"{text} days"
    # "3" with spaces / "3days" without space
    digits = "".join(c for c in text if c.isdigit())
    if digits and not _DURATION_UNIT_RE.search(text):
        return f"{digits} days"
    return text


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
