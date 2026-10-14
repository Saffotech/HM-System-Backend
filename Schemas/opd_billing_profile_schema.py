import re
from datetime import date, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

IST = ZoneInfo("Asia/Kolkata")
_PLACE_NAME = re.compile(r"^(?=.*[A-Za-z])[A-Za-z][A-Za-z .'-]*$")


class AddressInfo(BaseModel):
    line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


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


class OpdBillingProfileResponse(BaseModel):
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

    employee_id: Optional[str] = None
    qualification: Optional[str] = None
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

    model_config = ConfigDict(extra="forbid")

    @field_validator("city", "state")
    @classmethod
    def place_name_has_letters(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not _PLACE_NAME.fullmatch(cleaned):
            label = "City" if info.field_name == "city" else "State"
            raise PydanticCustomError(
                "invalid_place_name",
                "{label} must contain letters, not only numbers or symbols",
                {"label": label},
            )
        return cleaned


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")


class OpdBillingProfileUpdate(BaseModel):
    """OPD Billing-editable fields only."""

    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: Optional[int] = Field(None, ge=0, le=60)
    bio: Optional[str] = None
    languages: Optional[List[str]] = None

    phone: Optional[str] = Field(None, max_length=20)
    phone_code: Optional[str] = Field(None, max_length=10)
    address: Optional[AddressUpdate] = None
    date_of_birth: Optional[date] = None
    gender: Optional[int] = Field(None, ge=1, le=4)
    emergency_contact: Optional[EmergencyContactUpdate] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_not_in_future(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > datetime.now(IST).date():
            raise PydanticCustomError(
                "date_of_birth_future",
                "Date of birth cannot be in the future",
            )
        return value


class OpdBillingProfileImageResponse(BaseModel):
    message: str
    profile_image_url: Optional[str] = None
