from datetime import date, datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from Models.audit_log import AuditLog
from Models.user import User
from Schemas.audit_schema import AuditLogEntry
from Services.role_policy import caller_role_name

IST = ZoneInfo("Asia/Kolkata")


def log_event(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    summary: str,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        actor_role=caller_role_name(actor) if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()


def _to_entry(row: AuditLog) -> AuditLogEntry:
    return AuditLogEntry(
        id=row.id,
        actor_id=row.actor_id,
        actor_email=row.actor_email,
        actor_role=row.actor_role,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        summary=row.summary,
        details=row.details,
        ip_address=row.ip_address,
        created_at=row.created_at,
    )


def list_audit_logs(
    db: Session,
    *,
    search: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q = db.query(AuditLog)

    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            AuditLog.summary.ilike(term) | AuditLog.actor_email.ilike(term)
        )

    if action:
        q = q.filter(AuditLog.action == action)

    if actor_id is not None:
        q = q.filter(AuditLog.actor_id == actor_id)

    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        q = q.filter(AuditLog.created_at >= start)

    if date_to is not None:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        q = q.filter(AuditLog.created_at <= end)

    total = q.count()
    rows = (
        q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "entries": [_to_entry(r) for r in rows],
    }
