from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.hospital_settings import SETTINGS_ROW_ID, HospitalSettings
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


def get_settings_row(db: Session) -> HospitalSettings:
    row = db.query(HospitalSettings).filter(HospitalSettings.id == SETTINGS_ROW_ID).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Hospital settings not found. Run python seed.py to create the default row.",
        )
    return row


def ensure_default_settings(db: Session) -> HospitalSettings:
    row = db.query(HospitalSettings).filter(HospitalSettings.id == SETTINGS_ROW_ID).first()
    if row:
        return row

    row = HospitalSettings(id=SETTINGS_ROW_ID, name="")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_settings(db: Session) -> HospitalSettingsOut:
    return _to_out(get_settings_row(db))


def update_settings(
    db: Session,
    data: HospitalSettingsUpdate,
    actor: User,
) -> HospitalSettingsOut:
    row = get_settings_row(db)
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
