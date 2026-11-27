from datetime import date

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class UserCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name:  Optional[str] = None
    email:      EmailStr
    password:   str = Field(..., min_length=8)
    role_id:    int  # FK to roles table
    department_id: Optional[int] = None  # Required for Doctor only; unused for Nurse (bed allocation assigns responsibility)
    phone: Optional[str] = Field(None, max_length=20)
    specialization: Optional[str] = Field(None, max_length=120)
    gender: Optional[int] = Field(None, ge=1, le=4)
    date_of_birth: Optional[date] = None
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    medical_license_number: Optional[str] = Field(None, max_length=100)
    consultation_fee: Optional[float] = Field(None, ge=0)


class PatientSelfRegister(BaseModel):
    """Public signup. Creates the login and the patients row. No visit or bill."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = None
    phone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    date_of_birth: date
    gender: int = Field(..., ge=1, le=4)
    aadhaar_number: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")
    address: Optional[str] = None
    state: Optional[str] = None
    blood_group: Optional[str] = Field(None, max_length=5)
    allergies: Optional[str] = None
    insurance_policy_no: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = Field(None, max_length=50)
    hospital_code: str = Field(..., min_length=1, max_length=50)


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    """Signed-in user changes their own password."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=72)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RoleCreate(BaseModel):
    name:        str
    description: Optional[str] = None

class PermissionCreate(BaseModel):
    name:        str  # "patients:view"
    description: Optional[str] = None

class AssignPermissions(BaseModel):
    permission_ids: List[int]

class RoleResponse(BaseModel):
    id:          int
    name:        str
    description: Optional[str]
    permissions: List[str] = []

    class Config:
        from_attributes = True