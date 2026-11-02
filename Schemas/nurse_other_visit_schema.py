from typing import List, Optional

from pydantic import BaseModel


class DepartmentOption(BaseModel):
    id: int
    name: str
    code: Optional[str] = None


class DepartmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    departments: List[DepartmentOption]
