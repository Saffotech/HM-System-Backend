from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


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


class StaffActivateRequest(BaseModel):
    is_active: bool


class StaffUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    phone: Optional[str] = None


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
