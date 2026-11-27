from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRequestCreate(BaseModel):
    confirm_live_recipient: bool = False
    expected_recipient_email: str | None = None


class ResubmissionCreate(DocumentRequestCreate):
    document_ids: list[int] = Field(default_factory=list)


class AdditionalDocumentsCreate(DocumentRequestCreate):
    codes: list[str]


class DocumentRequestQueued(BaseModel):
    message: str
    case_id: int
    request_id: int
    email_job_id: int | None = None
    email_status: str | None = None
    expires_at: datetime | None = None
    duplicate: bool = False
