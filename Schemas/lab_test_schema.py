from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class LabTestCreate(BaseModel):
    test_name: str = Field(..., min_length=1, max_length=255)
    department_id: int = Field(..., gt=0)
    price: Decimal = Field(..., ge=0, decimal_places=2, max_digits=10)


class LabTestUpdate(BaseModel):
    test_name: Optional[str] = Field(None, min_length=1, max_length=255)
    department_id: Optional[int] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=2, max_digits=10)


class LabTestActivation(BaseModel):
    active: bool


class LabTestResponse(BaseModel):
    id: int
    test_name: str
    department_id: int
    price: Decimal
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LabTestListResponse(BaseModel):
    total: int
    tests: List[LabTestResponse]
