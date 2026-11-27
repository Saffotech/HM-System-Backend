from pydantic import BaseModel, Field


class DocumentTypeCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=80)
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = None
    requirement_type: str
    is_required: bool = True
    is_active: bool = True
    allowed_file_types: list[str]
    max_file_size_mb: int = Field(5, ge=1, le=5)
    display_order: int = 0


class DocumentTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_required: bool | None = None
    allowed_file_types: list[str] | None = None
    max_file_size_mb: int | None = Field(None, ge=1, le=5)
    display_order: int | None = None


class DocumentTypeStatus(BaseModel):
    is_active: bool


class DocumentTypeOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    requirement_type: str
    is_required: bool
    is_active: bool
    allowed_file_types: list[str]
    max_file_size_mb: int
    display_order: int

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row.id,
            code=row.code,
            name=row.name,
            description=row.description,
            requirement_type=row.requirement_type,
            is_required=row.is_required,
            is_active=row.is_active,
            allowed_file_types=[part.strip() for part in (row.allowed_file_types or "").split(",") if part.strip()],
            max_file_size_mb=row.max_file_size_mb,
            display_order=row.display_order,
        )
