"""Shared helpers for server-side audit metadata (never trust client-supplied IP/UA)."""
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from Models.user import User
from Services import audit_service


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


def user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    raw = (request.headers.get("user-agent") or "").strip()
    if not raw:
        return None
    return raw[:512]


def safe_log_event(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    summary: str,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Write audit row without failing the caller's business transaction."""
    try:
        audit_service.log_event(
            db,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            summary=summary,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
