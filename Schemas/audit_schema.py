from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    summary: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    page: int
    limit: int
    entries: List[AuditLogEntry]
