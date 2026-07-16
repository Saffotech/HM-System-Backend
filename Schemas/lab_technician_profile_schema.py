from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AddressInfo(BaseModel):
    line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class EmergencyContactInfo(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class DepartmentInfo(BaseModel):
    id: int
    name: str


class RoleInfo(BaseModel):
    id: int
    name: str


class ShiftInfo(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class LabTechnicianProfileResponse(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    phone_code: Optional[str] = None

    address: AddressInfo
    date_of_birth: Optional[date] = None
    gender: Optional[int] = None
    emergency_contact: EmergencyContactInfo

    department: Optional[DepartmentInfo] = None
    role: Optional[RoleInfo] = None

    qualification: Optional[str] = None
    license_number: Optional[str] = None
    employee_id: Optional[str] = None
    experience_years: Optional[int] = None
    joining_date: Optional[date] = None
    bio: Optional[str] = None
    languages: List[str] = Field(default_factory=list)

    shift: Optional[ShiftInfo] = None

    profile_image_url: Optional[str] = None
    is_profile_completed: bool = False
    profile_completion_percentage: int = 0

    is_active: bool = True
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AddressUpdate(BaseModel):
    line: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")


class LabTechnicianProfileUpdate(BaseModel):
    """Lab technician-editable fields only. Admin fields are rejected by schema."""

    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: Optional[int] = Field(None, ge=0, le=60)
    bio: Optional[str] = None
    languages: Optional[List[str]] = None
    license_number: Optional[str] = Field(None, max_length=100)

    phone: Optional[str] = Field(None, max_length=20)
    phone_code: Optional[str] = Field(None, max_length=10)
    address: Optional[AddressUpdate] = None
    date_of_birth: Optional[date] = None
    gender: Optional[int] = Field(None, ge=1, le=4)
    emergency_contact: Optional[EmergencyContactUpdate] = None

    model_config = ConfigDict(extra="forbid")


class LabTechnicianProfileImageResponse(BaseModel):
    message: str
    profile_image_url: Optional[str] = None
