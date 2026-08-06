"""IPD profile request/response schemas — mirrors OPD billing profile shape."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleInfo(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


class DepartmentInfo(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


class ShiftInfo(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class AddressInfo(BaseModel):
    line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None


class EmergencyContactInfo(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    relation: Optional[str] = None


class IpdProfileUpdate(BaseModel):
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    bio: Optional[str] = None
    languages: Optional[List[str]] = None
    phone: Optional[str] = None
    phone_code: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[int] = None


class IpdProfileResponse(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_code: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[int] = None
    qualification: Optional[str] = None
    employee_id: Optional[str] = None
    experience_years: Optional[int] = None
    joining_date: Optional[date] = None
    bio: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    profile_image_url: Optional[str] = None
    is_profile_completed: bool = False
    role: Optional[RoleInfo] = None
    department: Optional[DepartmentInfo] = None
    shift: Optional[ShiftInfo] = None
    address: Optional[AddressInfo] = None
    emergency_contact: Optional[EmergencyContactInfo] = None
    updated_at: Optional[datetime] = None


class IpdProfileImageResponse(BaseModel):
    profile_image_url: Optional[str] = None
    message: str
