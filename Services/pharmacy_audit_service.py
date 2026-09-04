"""Audit logging for Pharmacy actions (Super Admin reads via GET /super-admin/audit)."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from Models.user import User
from Services.audit_helpers import safe_log_event


def _attr(obj: Any, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _item_snapshot(items: Any) -> list[dict[str, Any]]:
    if not items:
        return []
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "prescription_item_id": _attr(item, "prescription_item_id"),
                "medicine_name": _attr(item, "medicine_name"),
                "quantity_dispensed": _attr(item, "quantity_dispensed"),
                "quantity_prescribed": _attr(item, "quantity_prescribed"),
                "quantity_remaining": _attr(item, "quantity_remaining"),
                "unit_price": _attr(item, "unit_price"),
                "amount": _attr(item, "amount"),
            }
        )
    return rows


def log_dispense(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    prescription_id: int,
    result: Any,
    batch_number: Optional[str] = None,
    remarks: Optional[str] = None,
) -> None:
    dispensing_id = _attr(result, "dispensing_id")
    total_amount = _attr(result, "total_amount")
    status = _attr(result, "status")
    items = _item_snapshot(_attr(result, "items"))
    safe_log_event(
        db,
        actor=actor,
        action="pharmacy.dispense",
        resource_type="pharmacy_dispensing",
        resource_id=dispensing_id,
        summary=(
            f"Pharmacy dispensed prescription {prescription_id}"
            + (f" amount={total_amount}" if total_amount is not None else "")
            + (f" status={status}" if status else "")
        ),
        details={
            "dispensing_id": dispensing_id,
            "prescription_id": prescription_id,
            "status": status,
            "total_amount": total_amount,
            "batch_number": batch_number,
            "remarks": remarks,
            "item_count": len(items),
            "items": items,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
