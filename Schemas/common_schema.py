from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    total: int
    page: int
    page_size: int
    items: List[T]


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
