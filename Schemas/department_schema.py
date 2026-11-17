
from typing import List, Literal, Optional
import re

from pydantic import BaseModel, Field, field_validator, ConfigDict

DepartmentKind = Literal["doctor", "lab"]


def validate_department_name(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Department name cannot be empty")

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]*", value):
        raise ValueError(
            "Department name must start with a letter "
            "and contain only letters, numbers, and spaces"
        )

    return value


def validate_department_code(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None

    value = value.strip()

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", value):
        raise ValueError(
            "Department code must start with a letter "
            "and contain only letters and numbers"
        )

    return value


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)
    kind: DepartmentKind = "doctor"

    _validate_name = field_validator("name")(
        validate_department_name
    )

    _validate_code = field_validator("code")(
        validate_department_code
    )


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=500)
    kind: Optional[DepartmentKind] = None
    is_active: Optional[bool] = None

    _validate_name = field_validator("name")(
        validate_department_name
    )

    _validate_code = field_validator("code")(
        validate_department_code
    )


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    kind: DepartmentKind = "doctor"
    is_active: bool


class DepartmentListResponse(BaseModel):
    total: int
    departments: List[DepartmentOut]


class DepartmentActionResponse(BaseModel):
    message: str
    department: DepartmentOut
