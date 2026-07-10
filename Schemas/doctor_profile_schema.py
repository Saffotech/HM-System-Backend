from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DoctorProfileResponse(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[int] = None
    emergency_contact_phone: Optional[str] = None
    is_active: bool = True

    department: Optional[str] = None
    specialization: Optional[str] = None

    qualification: Optional[str] = None
    medical_license_number: Optional[str] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    bio: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    profile_image_url: Optional[str] = None
    is_profile_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class DoctorProfileUpdate(BaseModel):
    """Doctor-editable fields only. Admin fields are rejected by schema."""

    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: Optional[int] = Field(None, ge=0, le=60)
    bio: Optional[str] = None
    languages: Optional[List[str]] = None

    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[int] = Field(None, ge=1, le=4)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")


class DoctorProfileImageResponse(BaseModel):
    message: str
    profile_image_url: Optional[str] = None
