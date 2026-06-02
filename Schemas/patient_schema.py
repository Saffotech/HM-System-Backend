"""Patient-related request/response schemas."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

GENDER_CODE_TO_LABEL = {
    1: "Male",
    2: "Female",
    3: "Other",
    4: "Prefer not to say",
}


def gender_code_to_label(gender: Optional[int]) -> Optional[str]:
    if gender is None:
        return None
    return GENDER_CODE_TO_LABEL.get(gender, str(gender))


class PatientFields(BaseModel):
    """Core patient demographics (no visit/billing)."""

    first_name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=15)
    last_name: Optional[str] = None
    gender: Optional[int] = Field(None, ge=1, le=4)
    blood_group: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    state: Optional[str] = None
    aadhaar_number: Optional[str] = None
    email: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    allergies: Optional[str] = None
    insurance_policy_no: Optional[str] = None


class PatientUpdate(BaseModel):
    """All fields optional — only sent fields are updated."""

    first_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=15)
    last_name: Optional[str] = None
    gender: Optional[int] = Field(None, ge=1, le=4)
    blood_group: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    state: Optional[str] = None
    aadhaar_number: Optional[str] = None
    email: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    allergies: Optional[str] = None
    insurance_policy_no: Optional[str] = None


class PatientOut(BaseModel):
    id: int
    patient_uid: str
    first_name: str
    last_name: Optional[str]
    phone: str
    gender: Optional[str]
    blood_group: Optional[str]
    date_of_birth: Optional[date]
    address: Optional[str]
    state: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True
