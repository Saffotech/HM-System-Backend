from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class PlatformStaffCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["crm", "accountant"]


class PlatformStaffOut(BaseModel):
    message: str
    user_id: int
    first_name: str
    last_name: Optional[str]
    email: str
    role: str
    tenant_id: Optional[int]
    is_active: bool


class PlatformStaffItem(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str]
    email: str
    role: str
    tenant_id: Optional[int]
    is_active: bool
