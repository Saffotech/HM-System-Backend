from datetime import datetime

from pydantic import BaseModel


class EmailJobOut(BaseModel):
    id: int
    job_type: str
    case_id: int | None = None
    document_request_id: int | None = None
    recipient_email: str
    recipient_name: str | None = None
    status: str
    attempt_count: int
    next_retry_at: datetime | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None
    sanitized_error: str | None = None
