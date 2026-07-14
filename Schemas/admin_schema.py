from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class StaffListItem(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None


class StaffListResponse(BaseModel):
    total: int
    page: int
    limit: int
    staff: List[StaffListItem]


class StaffDetailOut(StaffListItem):
    phone: Optional[str] = None
    login_count: int = 0
    specialization: Optional[str] = None
    medical_license_number: Optional[str] = None
    consultation_fee: Optional[float] = None
    is_profile_completed: Optional[bool] = None
    shift_name: Optional[str] = None
    shift_start_time: Optional[str] = None
    shift_end_time: Optional[str] = None


class StaffActivateRequest(BaseModel):
    is_active: bool


class StaffUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    phone: Optional[str] = None
    specialization: Optional[str] = None
    medical_license_number: Optional[str] = None
    consultation_fee: Optional[float] = Field(None, ge=0)
    # Admin-owned nurse shift fields
    shift_name: Optional[str] = Field(None, max_length=100)
    shift_start_time: Optional[str] = Field(None, max_length=10)
    shift_end_time: Optional[str] = Field(None, max_length=10)


class StaffActionResponse(BaseModel):
    message: str
    user_id: int


class StaffByRoleItem(BaseModel):
    role_id: int
    role_name: str
    count: int


class AdminDashboardResponse(BaseModel):
    total_staff: int
    active_staff: int
    inactive_staff: int
    total_departments: int
    total_roles: int
    staff_by_role: List[StaffByRoleItem]
