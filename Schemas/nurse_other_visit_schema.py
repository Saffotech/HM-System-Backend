from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OtherVisitCreate(BaseModel):
    patient_id: int = Field(..., ge=1)
    department_id: int = Field(..., ge=1)
    person_name: str = Field(..., min_length=1, max_length=255)
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None


class OtherVisitUpdate(BaseModel):
    department_id: Optional[int] = Field(None, ge=1)
    person_name: Optional[str] = Field(None, min_length=1, max_length=255)
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None


class OtherVisitVoidRequest(BaseModel):
    void_reason: str = Field(..., min_length=3, max_length=500)


class OtherVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    department_id: int
    department_name: str
    person_name: str
    visited_at: datetime
    notes: Optional[str] = None
    visit_number: Optional[int] = None
    recorded_by: int
    recorded_by_name: str
    created_at: datetime
    updated_by: Optional[int] = None
    updated_by_name: Optional[str] = None
    updated_at: Optional[datetime] = None
    is_voided: bool = False

    model_config = {"from_attributes": True}


class OtherVisitListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[OtherVisitResponse]


class DepartmentOption(BaseModel):
    id: int
    name: str
    code: Optional[str] = None


class DepartmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    departments: List[DepartmentOption]
