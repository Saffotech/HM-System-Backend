from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class UserCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name:  Optional[str] = None
    email:      EmailStr
    password:   str = Field(..., min_length=8)
    role_id:    int  # FK to roles table
    department_id: Optional[int] = None  # only relevant for Doctor/Nurse

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