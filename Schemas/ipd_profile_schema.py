"""IPD profile request/response schemas — mirrors OPD billing profile shape."""
import re
from datetime import date, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

IST = ZoneInfo("Asia/Kolkata")
_HAS_LETTER = re.compile(r"[A-Za-z]")


def _require_letter(value: Optional[str], label: str) -> Optional[str]:
    """Blank stays allowed. A non-blank value must include a letter."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _HAS_LETTER.search(cleaned):
        raise PydanticCustomError(
            "invalid_text",
            "{label} must contain letters, not only numbers or symbols",
            {"label": label},
        )
    return cleaned


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
    line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class EmergencyContactInfo(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class AddressUpdate(BaseModel):
    line: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("line")
    @classmethod
    def address_has_letters(cls, value: Optional[str]) -> Optional[str]:
        return _require_letter(value, "Address")

    @field_validator("city", "state")
    @classmethod
    def place_has_letters(cls, value: Optional[str], info) -> Optional[str]:
        label = "City" if info.field_name == "city" else "State"
        return _require_letter(value, label)


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_has_letters(cls, value: Optional[str]) -> Optional[str]:
        return _require_letter(value, "Emergency contact name")


class IpdProfileUpdate(BaseModel):
    """IPD-editable fields only (admin-owned identity stays read-only)."""

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

    @field_validator("qualification")
    @classmethod
    def qualification_has_letters(cls, value: Optional[str]) -> Optional[str]:
        return _require_letter(value, "Qualification")

    @field_validator("bio")
    @classmethod
    def bio_has_letters(cls, value: Optional[str]) -> Optional[str]:
        return _require_letter(value, "Bio")


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
    profile_completion_percentage: int = 0
    is_active: bool = True
    role: Optional[RoleInfo] = None
    department: Optional[DepartmentInfo] = None
    shift: Optional[ShiftInfo] = None
    address: Optional[AddressInfo] = None
    emergency_contact: Optional[EmergencyContactInfo] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IpdProfileImageResponse(BaseModel):
    profile_image_url: Optional[str] = None
    message: str
