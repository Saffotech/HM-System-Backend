from datetime import date

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class UserCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name:  Optional[str] = None
    email:      EmailStr
    password:   str = Field(..., min_length=8)
    role_id:    int  # FK to roles table
    department_id: Optional[int] = None  # only relevant for Doctor
    phone: Optional[str] = Field(None, max_length=20)
    specialization: Optional[str] = Field(None, max_length=120)
    gender: Optional[int] = Field(None, ge=1, le=4)
    date_of_birth: Optional[date] = None
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    medical_license_number: Optional[str] = Field(None, max_length=100)
    consultation_fee: Optional[float] = Field(None, ge=0)


class UserLogin(BaseModel):
    email:    EmailStr
    password: str

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