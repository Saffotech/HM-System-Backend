from datetime import datetime

from pydantic import BaseModel


class PublicRequirement(BaseModel):
    item_id: int
    code: str
    name: str
    description: str | None = None
    is_required: bool
    allowed_file_types: list[str]
    max_file_size_mb: int
    status: str
    display_order: int
    remarks: str | None = None


class PublicRequestView(BaseModel):
    hospital_name: str
    expires_at: datetime
    requirements: list[PublicRequirement]
