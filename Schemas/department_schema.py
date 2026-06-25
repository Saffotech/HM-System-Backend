from typing import List, Optional

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class DepartmentOut(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class DepartmentListResponse(BaseModel):
    total: int
    departments: List[DepartmentOut]


class DepartmentActionResponse(BaseModel):
    message: str
    department: DepartmentOut
