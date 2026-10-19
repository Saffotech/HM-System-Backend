from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.hospital_settings import HospitalSettings
from Models.user import User
from Schemas.hospital_settings_schema import HospitalSettingsOut, HospitalSettingsUpdate
from Services import audit_service

IST = ZoneInfo("Asia/Kolkata")

_UPDATABLE_FIELDS = (
    "name",
    "tagline",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "phone",
    "email",
    "website",
    "gstin",
    "pan",
    "registration_number",
    "default_registration_fee",
    "default_consultation_fee",
    "default_gst_percent",
    "currency",
    "timezone",
)


def _to_out(row: HospitalSettings) -> HospitalSettingsOut:
    return HospitalSettingsOut(
        id=row.id,
        name=row.name,
        tagline=row.tagline,
        address_line1=row.address_line1,
        address_line2=row.address_line2,
        city=row.city,
        state=row.state,
        pincode=row.pincode,
        phone=row.phone,
        email=row.email,
        website=row.website,
        gstin=row.gstin,
        pan=row.pan,
        registration_number=row.registration_number,
        default_registration_fee=row.default_registration_fee,
        default_consultation_fee=row.default_consultation_fee,
        default_gst_percent=row.default_gst_percent,
        currency=row.currency,
        timezone=row.timezone,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


def _require_tenant_id(db: Session, tenant_id: int | None) -> int:
    resolved = tenant_id if tenant_id is not None else db.info.get("tenant_id")
    if resolved is None:
        raise HTTPException(status_code=400, detail="This account is not linked to a hospital")
    return resolved


def get_settings_row(db: Session, tenant_id: int | None = None) -> HospitalSettings:
    resolved = _require_tenant_id(db, tenant_id)
    row = (
        db.query(HospitalSettings)
        .filter(HospitalSettings.tenant_id == resolved)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Hospital settings not found")
    return row


def get_settings(db: Session, tenant_id: int | None = None) -> HospitalSettingsOut:
    return _to_out(get_settings_row(db, tenant_id))


def update_settings(
    db: Session,
    data: HospitalSettingsUpdate,
    actor: User,
) -> HospitalSettingsOut:
    row = get_settings_row(db, actor.tenant_id)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field in _UPDATABLE_FIELDS:
        if field in updates:
            setattr(row, field, updates[field])

    row.updated_at = datetime.now(IST)
    row.updated_by = actor.id
    db.commit()
    db.refresh(row)

    audit_service.log_event(
        db,
        actor=actor,
        action="settings.update",
        resource_type="hospital_settings",
        resource_id=row.id,
        summary=f"Updated hospital settings ({row.name or 'unnamed hospital'})",
        details={"fields": list(updates.keys())},
    )

    return _to_out(row)


def letterhead_for_tenant(db: Session, tenant_id: int) -> dict:
    row = (
        db.query(HospitalSettings)
        .filter(HospitalSettings.tenant_id == tenant_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Hospital settings not found")
    address = ", ".join(
        part
        for part in (
            row.address_line1,
            row.address_line2,
            row.city,
            row.state,
            row.pincode,
        )
        if part
    )
    return {
        "name": row.name,
        "address_line1": row.address_line1,
        "address_line2": row.address_line2,
        "city": row.city,
        "state": row.state,
        "pincode": row.pincode,
        "phone": row.phone,
        "email": row.email,
        "gstin": row.gstin or "",
        "address": address,
    }
