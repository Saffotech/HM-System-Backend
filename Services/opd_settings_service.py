from datetime import datetime
import math
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.opd_settings import OPD_SETTINGS_ROW_ID, OpdSettings
from Models.user import User
from Schemas.opd_settings_schema import (
    BankDetails,
    DeleteControlsOut,
    DiscountRefundOut,
    DiscountRefundUpdate,
    OpdSettingsOut,
    OpdSettingsUpdate,
    PaymentSettingsOut,
    PaymentSettingsUpdate,
    PricingOut,
    PricingUpdate,
)
from Services.admin_edit_policy import (
    GLOBAL_FEE_KEYS,
    merge_admin_edit_patch,
    normalize_admin_edit,
)
from Services import audit_service

IST = ZoneInfo("Asia/Kolkata")

# Roles that may delete even when OPD staff deletes are disabled.
_ADMIN_OVERRIDE_ROLES = frozenset({"admin", "super_admin"})

DEFAULT_PRICING: dict[str, Any] = {
    "registration_fee": 200.0,
    "consultation_fee": 500.0,
    "gst_percent": 5.0,
    "allow_manual_price_entry": True,
    "bed_tariff": {
        "general_ward_charge": 500.0,
        "private_ward_charge": 2000.0,
        "icu_charge": 5000.0,
        "ward_rates": [],
        "special_bed_rates": [],
    },
    "department_consultation_fees": [],
    "doctor_consultation_fees": [],
    "bill_items": [],
}

DEFAULT_DISCOUNT_REFUND: dict[str, Any] = {
    "allow_discount": True,
    "max_discount_percent": 10.0,
    "require_admin_approval_for_discount": True,
    "allow_refund": True,
    "require_admin_approval_for_refund": True,
    "allow_cancel_paid_bill": False,
}

DEFAULT_PAYMENT_MODES: dict[str, Any] = {
    "modes": [
        {"code": "cash", "label": "Cash", "enabled": True},
        {"code": "card", "label": "Card", "enabled": True},
        {"code": "upi", "label": "UPI", "enabled": True},
        {"code": "insurance", "label": "Insurance", "enabled": True},
    ],
    "bank_details": {
        "account_name": "",
        "bank_name": "",
        "account_number": "",
        "ifsc": "",
        "upi_id": "",
    },
    "insurance_providers": [],
}

DEFAULT_APPOINTMENT_SLOTS: dict[str, Any] = {
    "start_time": "09:00",
    "end_time": "16:30",
    "slot_duration_minutes": 30,
    "working_days": ["mon", "tue", "wed", "thu", "fri", "sat"],
    "doctor_slots": [],
}

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _role_name(user: Optional[User]) -> str:
    if not user or not user.role_obj:
        return ""
    return (user.role_obj.name or "").strip().lower()



def ensure_opd_settings(db: Session) -> OpdSettings:
    row = db.query(OpdSettings).filter(OpdSettings.id == OPD_SETTINGS_ROW_ID).first()
    if row:
        return row
    row = OpdSettings(
        id=OPD_SETTINGS_ROW_ID,
        allow_patient_delete=True,
        allow_appointment_delete=True,
        allow_unpaid_bill_delete=True,
        require_admin_approval_for_delete=True,
        extra={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_settings_row(db: Session) -> OpdSettings:
    return ensure_opd_settings(db)


def get_admin_edit_controls(db: Session) -> dict[str, bool]:
    row = get_settings_row(db)
    extra = row.extra if isinstance(row.extra, dict) else {}
    return normalize_admin_edit(extra.get("admin_edit"))


def assert_admin_may_edit_bed_section(db: Session, actor: User, section: str) -> None:
    """Block Hospital Admin bed writes when Super Admin locked the section card."""
    if _role_name(actor) == "super_admin":
        return
    locks = get_admin_edit_controls(db)
    if not locks.get(section, True):
        labels = {
            "bed_inventory": "Bed inventory",
            "wards": "Wards",
            "all_beds": "All beds",
        }
        label = labels.get(section, section)
        raise HTTPException(
            status_code=403,
            detail=f"{label} is locked by Super Admin",
        )


def assert_admin_may_edit_bed_inventory(db: Session, actor: User) -> None:
    assert_admin_may_edit_bed_section(db, actor, "bed_inventory")


def default_pricing() -> PricingOut:
    return PricingOut.model_validate(DEFAULT_PRICING)


def normalize_pricing(raw: Any) -> PricingOut:
    """Coerce stored / partial pricing into a complete PricingOut (never null)."""
    base = dict(DEFAULT_PRICING)
    if isinstance(raw, PricingOut):
        return raw
    if isinstance(raw, dict):
        for key in DEFAULT_PRICING:
            if key in raw and raw[key] is not None:
                base[key] = raw[key]
    try:
        return PricingOut.model_validate(base)
    except Exception:
        # Corrupt stored data must not break billing — fall back to safe defaults.
        return default_pricing()


def get_pricing(db: Session) -> PricingOut:
    row = get_settings_row(db)
    extra = row.extra if isinstance(row.extra, dict) else {}
    return normalize_pricing(extra.get("pricing"))


def default_discount_refund() -> DiscountRefundOut:
    return DiscountRefundOut.model_validate(DEFAULT_DISCOUNT_REFUND)


def normalize_discount_refund(raw: Any) -> DiscountRefundOut:
    """Coerce stored / partial discount_refund into a complete typed model."""
    base = dict(DEFAULT_DISCOUNT_REFUND)
    if isinstance(raw, DiscountRefundOut):
        return raw
    if isinstance(raw, dict):
        for key in DEFAULT_DISCOUNT_REFUND:
            if key in raw and raw[key] is not None:
                base[key] = raw[key]
    try:
        return DiscountRefundOut.model_validate(base)
    except Exception:
        return default_discount_refund()


def get_discount_settings(db: Session) -> DiscountRefundOut:
    row = get_settings_row(db)
    extra = row.extra if isinstance(row.extra, dict) else {}
    return normalize_discount_refund(extra.get("discount_refund"))


def _is_admin(user: Optional[User]) -> bool:
    return _role_name(user) in _ADMIN_OVERRIDE_ROLES


def validate_discount(
    db: Session,
    *,
    current_user: User,
    discount_percent: float,
) -> None:
    """
    Enforce Admin discount controls. Call before applying any discount.

    Raises HTTPException if discount is not allowed or exceeds the limit.
    """
    if discount_percent <= 0:
        return

    settings = get_discount_settings(db)

    if not settings.allow_discount:
        raise HTTPException(
            status_code=403,
            detail="Discount is disabled by Administrator.",
        )

    cap = float(settings.max_discount_percent)
    if discount_percent > cap + 0.009:
        if not _is_admin(current_user):
            raise HTTPException(
                status_code=400,
                detail=f"Maximum allowed discount is {cap:.0f}%.",
            )

    if settings.require_admin_approval_for_discount and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Discount requires Administrator approval.",
        )


def validate_refund(
    db: Session,
    *,
    current_user: User,
) -> None:
    """
    Enforce Admin refund controls. Call before processing any refund.

    Raises HTTPException if refund is not allowed or requires approval.
    """
    settings = get_discount_settings(db)

    if not settings.allow_refund:
        raise HTTPException(
            status_code=403,
            detail="Refund is disabled by Administrator.",
        )

    if settings.require_admin_approval_for_refund and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Refund requires Administrator approval.",
        )


def validate_paid_bill_cancellation(
    db: Session,
    *,
    current_user: User,
) -> None:
    """
    Enforce allow_cancel_paid_bill setting.
    Only Admin/Super Admin may cancel paid bills when the setting is true.
    """
    settings = get_discount_settings(db)

    if not settings.allow_cancel_paid_bill:
        raise HTTPException(
            status_code=403,
            detail="Cancellation of paid bills is disabled by Administrator.",
        )

    if not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only Administrator can cancel paid bills.",
        )


def default_payment_settings() -> PaymentSettingsOut:
    return PaymentSettingsOut.model_validate(DEFAULT_PAYMENT_MODES)


def normalize_payment_settings(raw: Any) -> PaymentSettingsOut:
    """Coerce stored / partial payment_modes into a complete typed model."""
    base = dict(DEFAULT_PAYMENT_MODES)
    if isinstance(raw, PaymentSettingsOut):
        return raw
    if isinstance(raw, dict):
        for key in DEFAULT_PAYMENT_MODES:
            if key in raw and raw[key] is not None:
                base[key] = raw[key]
    try:
        return PaymentSettingsOut.model_validate(base)
    except Exception:
        return default_payment_settings()


def get_payment_settings(db: Session) -> PaymentSettingsOut:
    row = get_settings_row(db)
    extra = row.extra if isinstance(row.extra, dict) else {}
    return normalize_payment_settings(extra.get("payment_modes"))


def is_payment_mode_enabled(settings: PaymentSettingsOut, mode: str) -> bool:
    key = (mode or "").strip().lower()
    for m in settings.modes:
        if m.code == key:
            return m.enabled
    return True


def get_active_insurance_providers(settings: PaymentSettingsOut) -> list:
    return [p for p in settings.insurance_providers if p.is_active]


def get_bank_details(db: Session) -> BankDetails:
    return get_payment_settings(db).bank_details


def validate_payment_mode(
    db: Session,
    *,
    payment_mode: str,
) -> None:
    """
    Enforce Admin payment mode controls. Call before processing any payment.
    Raises HTTPException if the selected payment mode is disabled.
    """
    key = (payment_mode or "").strip().lower()
    if not key:
        return

    settings = get_payment_settings(db)

    if not is_payment_mode_enabled(settings, key):
        label = key.upper() if key == "upi" else key.capitalize()
        raise HTTPException(
            status_code=403,
            detail=f"{label} payment is disabled by Administrator.",
        )

    if key == "insurance":
        if not any(p.is_active for p in settings.insurance_providers):
            pass


def validate_insurance_provider(
    db: Session,
    *,
    provider_code: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> None:
    """
    Validate that the insurance provider exists and is active.
    Call when payment_mode is 'insurance' and a provider is specified.
    """
    if not provider_code and not provider_name:
        return

    settings = get_payment_settings(db)

    search = (provider_code or provider_name or "").strip().lower()
    found = None
    for p in settings.insurance_providers:
        if provider_code and p.code.lower() == search:
            found = p
            break
        if provider_name and p.name.lower() == search:
            found = p
            break

    if not found:
        raise HTTPException(
            status_code=400,
            detail="Insurance provider not found.",
        )

    if not found.is_active:
        raise HTTPException(
            status_code=400,
            detail="Insurance provider is inactive.",
        )


def resolve_bed_rate(
    pricing: PricingOut,
    *,
    bed_number: Optional[str] = None,
    ward_name: Optional[str] = None,
) -> float:
    """
    Resolve bed daily rate with priority:
    1) special_bed_rates (exact bed)
    2) ward_rates (exact ward)
    3) ward defaults (ICU / Private / General)
    """
    bed_tariff = pricing.bed_tariff if pricing and pricing.bed_tariff else None
    if not bed_tariff:
        return 0.0

    bed_key = str(bed_number or "").strip().lower()
    ward_key = str(ward_name or "").strip().lower()

    if bed_key:
        for row in bed_tariff.special_bed_rates or []:
            if str(row.bed_number or "").strip().lower() == bed_key:
                return float(row.charge_per_day)

    if ward_key:
        for row in bed_tariff.ward_rates or []:
            if str(row.ward_name or "").strip().lower() == ward_key:
                return float(row.charge_per_day)

    if "icu" in ward_key:
        return float(bed_tariff.icu_charge)
    if "private" in ward_key:
        return float(bed_tariff.private_ward_charge)
    return float(bed_tariff.general_ward_charge)


def calculate_bed_days(admitted_at: Optional[datetime]) -> int:
    """
    days = max(1, ceil((now - admitted_at) / 24h))
    """
    if not admitted_at:
        return 1
    now = datetime.now(IST)
    try:
        delta_seconds = max(0.0, (now - admitted_at).total_seconds())
    except TypeError:
        # Defensive fallback for naive/aware mismatch from legacy rows.
        delta_seconds = max(0.0, (now.replace(tzinfo=None) - admitted_at.replace(tzinfo=None)).total_seconds())
    return max(1, int(math.ceil(delta_seconds / 86400)))


def resolve_consultation_fee(
    pricing: PricingOut,
    *,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> float:
    """
    Resolve consultation fee: doctor → department → hospital default.
    First match wins.
    """
    if doctor_id is not None:
        doc_id = int(doctor_id)
        for row in pricing.doctor_consultation_fees or []:
            if int(row.doctor_id) == doc_id:
                return float(row.fee)

    if department_id is not None:
        dept_id = int(department_id)
        for row in pricing.department_consultation_fees or []:
            if int(row.department_id) == dept_id:
                return float(row.fee)

    return float(pricing.consultation_fee)


def resolve_visit_fees(
    pricing: PricingOut,
    *,
    doctor_id: int,
    department_id: int,
    registration_fee: float,
) -> tuple[float, float, float]:
    """
    Apply Admin pricing to a visit.

    - registration_fee: keep 0 (waived / revisit); otherwise use settings.
    - consultation_fee: always resolved via doctor → department → hospital.
    - gst_percent: always from settings.
    """
    reg = 0.0 if float(registration_fee or 0) == 0 else float(pricing.registration_fee)
    consult = resolve_consultation_fee(
        pricing, doctor_id=doctor_id, department_id=department_id
    )
    gst = float(pricing.gst_percent)
    return reg, consult, gst


def _active_bill_item_map(pricing: PricingOut) -> dict[str, float]:
    mapping: dict[str, float] = {}
    for item in pricing.bill_items or []:
        if not item.is_active:
            continue
        key = (item.name or "").strip().lower()
        if key:
            mapping[key] = float(item.price)
    return mapping


def validate_extra_bill_items(
    pricing: PricingOut,
    extra_items: Optional[list[dict]],
    *,
    strict: bool = True,
) -> list[dict]:
    """
    Normalize extra line items against Admin bill_items.

    When allow_manual_price_entry is False and strict=True, unit_price must match
    an active master item (by description/name). Unknown items are rejected.

    When strict=False (preserving existing bill lines), unknown items are kept
    so historical bills remain editable.
    """
    if not extra_items:
        return []

    allow_manual = bool(pricing.allow_manual_price_entry)
    master = _active_bill_item_map(pricing)
    normalized: list[dict] = []

    for item in extra_items:
        description = str(item.get("description") or "").strip()
        if not description:
            raise HTTPException(status_code=400, detail="Bill item description is required")
        try:
            qty = int(item.get("qty") or 1)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid bill item qty") from exc
        if qty < 1:
            raise HTTPException(status_code=400, detail="Bill item qty must be >= 1")

        try:
            unit_price = float(item.get("unit_price"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid bill item unit_price") from exc
        if unit_price < 0:
            raise HTTPException(status_code=400, detail="Bill item unit_price must be >= 0")

        key = description.lower()
        if not allow_manual:
            if key not in master:
                if strict:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Custom price entry is disabled. "
                            f"'{description}' is not in the Admin price master list."
                        ),
                    )
                # Grandfather existing line on unpaid bill updates.
            else:
                expected = master[key]
                if strict and abs(unit_price - expected) > 0.009:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Custom prices are disabled. "
                            f"'{description}' must use master price ₹{expected:.2f}."
                        ),
                    )
                unit_price = expected

        normalized.append(
            {
                "description": description,
                "qty": qty,
                "unit_price": unit_price,
            }
        )

    return normalized


def _merge_pricing_update(existing: PricingOut, incoming: dict[str, Any]) -> PricingOut:
    base = existing.model_dump()
    for key, value in incoming.items():
        if value is not None:
            base[key] = value
    return PricingOut.model_validate(base)


def _to_out(row: OpdSettings) -> OpdSettingsOut:
    extra = row.extra if isinstance(row.extra, dict) else {}
    return OpdSettingsOut(
        delete_controls=DeleteControlsOut(
            allow_patient_delete=bool(row.allow_patient_delete),
            allow_appointment_delete=bool(row.allow_appointment_delete),
            allow_unpaid_bill_delete=bool(row.allow_unpaid_bill_delete),
            require_admin_approval_for_delete=bool(row.require_admin_approval_for_delete),
        ),
        pricing=normalize_pricing(extra.get("pricing")),
        discount_refund=normalize_discount_refund(extra.get("discount_refund")),
        appointment_slots=extra.get("appointment_slots"),
        payment_modes=normalize_payment_settings(extra.get("payment_modes")),
        admin_edit=normalize_admin_edit(extra.get("admin_edit")),
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        updated_by=row.updated_by,
    )


def get_settings(db: Session) -> OpdSettingsOut:
    return _to_out(get_settings_row(db))


def update_settings(
    db: Session,
    data: OpdSettingsUpdate,
    actor: User,
) -> OpdSettingsOut:
    row = get_settings_row(db)
    requested = data.model_dump(exclude_unset=True)
    if not requested:
        raise HTTPException(status_code=400, detail="No fields to update")

    is_super_admin = _role_name(actor) == "super_admin"
    extra = dict(row.extra) if isinstance(row.extra, dict) else {}
    locks = normalize_admin_edit(extra.get("admin_edit"))
    updates = dict(requested)

    # Only Super Admin may change Admin-edit gates.
    admin_edit_changed = False
    if "admin_edit" in updates:
        updates.pop("admin_edit", None)
        if is_super_admin and data.admin_edit is not None:
            extra["admin_edit"] = merge_admin_edit_patch(locks, data.admin_edit)
            locks = normalize_admin_edit(extra["admin_edit"])
            admin_edit_changed = True

    # Hospital Admin cannot mutate locked cards — strip locked fields.
    if not is_super_admin:
        if "delete_controls" in updates and not locks.get("delete_controls", True):
            updates.pop("delete_controls", None)
        if "discount_refund" in updates and not locks.get("discount_refund", True):
            updates.pop("discount_refund", None)
        if "appointment_slots" in updates:
            # Slots payload is one blob; lock either hospital or doctor overrides by
            # forcing current stored value for locked parts.
            if not locks.get("hospital_default_slots", True) and not locks.get(
                "doctor_slot_overrides", True
            ):
                updates.pop("appointment_slots", None)
            elif "appointment_slots" in updates and updates["appointment_slots"] is not None:
                current_slots = (
                    extra.get("appointment_slots")
                    if isinstance(extra.get("appointment_slots"), dict)
                    else {}
                )
                incoming = dict(updates["appointment_slots"] or {})
                if not locks.get("hospital_default_slots", True):
                    for key in (
                        "start_time",
                        "end_time",
                        "slot_duration_minutes",
                        "working_days",
                    ):
                        if key in current_slots:
                            incoming[key] = current_slots[key]
                if not locks.get("doctor_slot_overrides", True):
                    incoming["doctor_slots"] = current_slots.get("doctor_slots", [])
                updates["appointment_slots"] = incoming
        if "payment_modes" in updates and updates.get("payment_modes") is not None:
            payment_update = dict(updates["payment_modes"] or {})
            current_pm = normalize_payment_settings(extra.get("payment_modes")).model_dump()
            if not locks.get("payment_modes", True):
                payment_update.pop("modes", None)
            if not locks.get("bank_upi_details", True):
                payment_update["bank_details"] = current_pm.get("bank_details")
            if not locks.get("insurance_providers", True):
                payment_update["insurance_providers"] = current_pm.get(
                    "insurance_providers", []
                )
            if payment_update:
                updates["payment_modes"] = payment_update
            else:
                updates.pop("payment_modes", None)
        if "pricing" in updates and updates.get("pricing") is not None:
            pricing_update = dict(updates["pricing"] or {})
            if not locks.get("global_fees_tax", True):
                for key in GLOBAL_FEE_KEYS:
                    pricing_update.pop(key, None)
            if not locks.get("bed_tariff", True):
                pricing_update.pop("bed_tariff", None)
            if not locks.get("consultation_fee_by_department", True):
                pricing_update.pop("department_consultation_fees", None)
            if not locks.get("consultation_fee_by_doctor", True):
                pricing_update.pop("doctor_consultation_fees", None)
            if not locks.get("bill_item_price_list", True):
                pricing_update.pop("bill_items", None)
            if pricing_update:
                updates["pricing"] = pricing_update
            else:
                updates.pop("pricing", None)

    if not updates and not admin_edit_changed:
        raise HTTPException(
            status_code=403 if not is_super_admin else 400,
            detail=(
                "These settings are locked by Super Admin"
                if not is_super_admin
                else "No fields to update"
            ),
        )

    before = {
        "allow_patient_delete": row.allow_patient_delete,
        "allow_appointment_delete": row.allow_appointment_delete,
        "allow_unpaid_bill_delete": row.allow_unpaid_bill_delete,
        "require_admin_approval_for_delete": row.require_admin_approval_for_delete,
    }

    delete_controls = updates.get("delete_controls") or {}
    if "allow_patient_delete" in delete_controls:
        row.allow_patient_delete = bool(delete_controls["allow_patient_delete"])
    if "allow_appointment_delete" in delete_controls:
        row.allow_appointment_delete = bool(delete_controls["allow_appointment_delete"])
    if "allow_unpaid_bill_delete" in delete_controls:
        row.allow_unpaid_bill_delete = bool(delete_controls["allow_unpaid_bill_delete"])
    if "require_admin_approval_for_delete" in delete_controls:
        row.require_admin_approval_for_delete = bool(
            delete_controls["require_admin_approval_for_delete"]
        )

    if "pricing" in updates and updates["pricing"] is not None:
        current = normalize_pricing(extra.get("pricing"))
        # Prefer stripped dict for Admin; full typed dump for Super Admin.
        if is_super_admin and isinstance(data.pricing, PricingUpdate):
            raw = data.pricing.model_dump(exclude_unset=True)
        else:
            raw = updates["pricing"] if isinstance(updates["pricing"], dict) else {}
        merged = _merge_pricing_update(current, raw)
        extra["pricing"] = merged.model_dump()

    if "discount_refund" in updates and updates["discount_refund"] is not None:
        current_dr = normalize_discount_refund(extra.get("discount_refund"))
        if isinstance(data.discount_refund, DiscountRefundUpdate):
            raw_dr = data.discount_refund.model_dump(exclude_unset=True)
        else:
            raw_dr = updates["discount_refund"]
        merged_dr = current_dr.model_dump()
        for k, v in (raw_dr if isinstance(raw_dr, dict) else {}).items():
            if v is not None:
                merged_dr[k] = v
        extra["discount_refund"] = DiscountRefundOut.model_validate(merged_dr).model_dump()

    if "payment_modes" in updates and updates["payment_modes"] is not None:
        current_pm = normalize_payment_settings(extra.get("payment_modes"))
        if isinstance(data.payment_modes, PaymentSettingsUpdate):
            raw_pm = data.payment_modes.model_dump(exclude_unset=True)
        else:
            raw_pm = updates["payment_modes"]
        merged_pm = current_pm.model_dump()
        for k, v in (raw_pm if isinstance(raw_pm, dict) else {}).items():
            if v is not None:
                merged_pm[k] = v
        extra["payment_modes"] = PaymentSettingsOut.model_validate(merged_pm).model_dump()

    for key in ("appointment_slots",):
        if key in updates and updates[key] is not None:
            extra[key] = updates[key]

    row.extra = extra
    row.updated_at = datetime.now(IST)
    row.updated_by = actor.id

    db.commit()
    db.refresh(row)

    after = {
        "allow_patient_delete": row.allow_patient_delete,
        "allow_appointment_delete": row.allow_appointment_delete,
        "allow_unpaid_bill_delete": row.allow_unpaid_bill_delete,
        "require_admin_approval_for_delete": row.require_admin_approval_for_delete,
    }
    audit_service.log_event(
        db,
        actor=actor,
        action="opd_settings.update",
        resource_type="opd_settings",
        resource_id=row.id,
        summary="Updated OPD settings",
        details={
            "before": before,
            "after": after,
            "pricing_updated": "pricing" in updates,
            "admin_edit_updated": admin_edit_changed,
        },
    )

    return _to_out(row)


def assert_delete_allowed(
    db: Session,
    *,
    current_user: User,
    kind: str,
) -> None:
    """
    Enforce Admin delete controls for non-admin callers.
    kind: 'patient' | 'appointment' | 'bill'
    """
    role = _role_name(current_user)
    if role in _ADMIN_OVERRIDE_ROLES:
        return

    row = get_settings_row(db)
    if kind == "patient":
        if not row.allow_patient_delete:
            raise HTTPException(
                status_code=403,
                detail="Patient deletion is disabled by Administrator.",
            )
        return
    if kind == "appointment":
        if not row.allow_appointment_delete:
            raise HTTPException(
                status_code=403,
                detail="Appointment deletion is disabled by Administrator.",
            )
        return
    if kind == "bill":
        if not row.allow_unpaid_bill_delete:
            raise HTTPException(
                status_code=403,
                detail="Bill deletion is disabled by Administrator.",
            )
        return

    raise HTTPException(status_code=400, detail=f"Unknown delete kind: {kind}")


def _parse_hhmm(value: Any, fallback: str) -> tuple[int, int]:
    text = str(value or fallback).strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not match:
        match = re.match(r"^(\d{1,2}):(\d{2})$", fallback)
    hours = min(23, max(0, int(match.group(1))))
    minutes = min(59, max(0, int(match.group(2))))
    return hours, minutes


def normalize_appointment_slots(raw: Any) -> dict[str, Any]:
    base = dict(DEFAULT_APPOINTMENT_SLOTS)
    if not isinstance(raw, dict):
        return base

    if raw.get("start_time"):
        base["start_time"] = str(raw["start_time"]).strip()
    if raw.get("end_time"):
        base["end_time"] = str(raw["end_time"]).strip()

    duration = raw.get("slot_duration_minutes")
    if duration is not None:
        try:
            parsed = int(duration)
            if 5 <= parsed <= 240:
                base["slot_duration_minutes"] = parsed
        except (TypeError, ValueError):
            pass

    if isinstance(raw.get("working_days"), list) and raw["working_days"]:
        base["working_days"] = [
            str(day).strip().lower()[:3]
            for day in raw["working_days"]
            if str(day).strip()
        ]

    doctor_slots = []
    for item in raw.get("doctor_slots") or []:
        if not isinstance(item, dict):
            continue
        try:
            doctor_id = int(item.get("doctor_id") or 0)
        except (TypeError, ValueError):
            continue
        if doctor_id <= 0:
            continue
        doctor_slots.append(
            {
                "doctor_id": doctor_id,
                "doctor_name": str(item.get("doctor_name") or "").strip(),
                "department_id": item.get("department_id"),
                "department_name": str(item.get("department_name") or "").strip(),
                "start_time": str(item.get("start_time") or base["start_time"]).strip(),
                "end_time": str(item.get("end_time") or base["end_time"]).strip(),
                "slot_duration_minutes": int(
                    item.get("slot_duration_minutes") or base["slot_duration_minutes"]
                ),
                "working_days": [
                    str(day).strip().lower()[:3]
                    for day in (item.get("working_days") or base["working_days"])
                    if str(day).strip()
                ],
            }
        )
    base["doctor_slots"] = doctor_slots
    return base


def get_appointment_slots(db: Session) -> dict[str, Any]:
    row = get_settings_row(db)
    extra = row.extra if isinstance(row.extra, dict) else {}
    return normalize_appointment_slots(extra.get("appointment_slots"))


def resolve_doctor_slot_settings(db: Session, doctor_id: int) -> dict[str, Any]:
    """Hospital default, overridden by per-doctor config when present."""
    config = get_appointment_slots(db)
    try:
        target_id = int(doctor_id)
    except (TypeError, ValueError):
        target_id = 0

    for override in config.get("doctor_slots") or []:
        if int(override.get("doctor_id") or 0) == target_id:
            return {
                "start_time": override.get("start_time") or config["start_time"],
                "end_time": override.get("end_time") or config["end_time"],
                "slot_duration_minutes": int(
                    override.get("slot_duration_minutes") or config["slot_duration_minutes"]
                ),
                "working_days": override.get("working_days") or config["working_days"],
            }

    return {
        "start_time": config["start_time"],
        "end_time": config["end_time"],
        "slot_duration_minutes": config["slot_duration_minutes"],
        "working_days": config["working_days"],
    }


def slot_weekday_key(day: datetime) -> str:
    return _WEEKDAY_KEYS[day.weekday()]


def iter_slot_datetimes(day: datetime, config: dict[str, Any]) -> list[datetime]:
    """Build slot start times from Admin OPD appointment slot settings."""
    start_h, start_m = _parse_hhmm(config.get("start_time"), "09:00")
    end_h, end_m = _parse_hhmm(config.get("end_time"), "16:30")
    duration = int(config.get("slot_duration_minutes") or 30)
    duration = max(5, min(240, duration))

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    if end_minutes <= start_minutes:
        return []

    slots: list[datetime] = []
    current = start_minutes
    while current + duration <= end_minutes:
        hour, minute = divmod(current, 60)
        slots.append(day.replace(hour=hour, minute=minute, second=0, microsecond=0))
        current += duration
    return slots

