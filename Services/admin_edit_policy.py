"""Super Admin gates for whether Hospital Admin may edit settings cards."""

from __future__ import annotations

from typing import Any, Iterable, Optional

DEFAULT_ADMIN_EDIT: dict[str, bool] = {
    # OPD
    "bed_inventory": True,
    "wards": True,
    "all_beds": True,
    "delete_controls": True,
    "global_fees_tax": True,
    "bed_tariff": True,
    "consultation_fee_by_department": True,
    "consultation_fee_by_doctor": True,
    "bill_item_price_list": True,
    "discount_refund": True,
    "hospital_default_slots": True,
    "doctor_slot_overrides": True,
    "payment_modes": True,
    "bank_upi_details": True,
    "insurance_providers": True,
    # Doctor
    "doctor_access": True,
    "doctor_clinical": True,
    "doctor_profile": True,
    # Receptionist
    "receptionist_access": True,
    "receptionist_profile": True,
    # LAB
    "lab_access": True,
    "lab_results": True,
    "lab_profile": True,
    # Nurse
    "nurse_access": True,
    "nurse_clinical": True,
    "nurse_operations": True,
    # Pharmacy
    "pharmacy_access": True,
    "pharmacy_dispense": True,
    "pharmacy_profile": True,
}

GLOBAL_FEE_KEYS = (
    "registration_fee",
    "consultation_fee",
    "gst_percent",
    "allow_manual_price_entry",
)

MODULE_CARD_PERMISSION_KEYS: dict[str, frozenset[str]] = {
    "doctor_access": frozenset(
        {
            "appointments:view",
            "patients:view",
            "notifications:view",
            "notifications:update",
        }
    ),
    "doctor_clinical": frozenset(
        {
            "appointments:update",
            "prescriptions:create",
            "prescriptions:update",
            "prescriptions:delete",
            "lab:view",
            "lab:create",
        }
    ),
    "doctor_profile": frozenset(
        {
            "doctor_profile:view",
            "doctor_profile:update",
            "doctor_profile:upload_image",
            "doctor_profile:delete_image",
        }
    ),
    "receptionist_access": frozenset(
        {
            "receptionist:view_queues",
            "receptionist:view_doctor_schedule",
            "notifications:view",
            "notifications:update",
        }
    ),
    "receptionist_profile": frozenset(
        {
            "receptionist_profile:view",
            "receptionist_profile:update",
            "receptionist_profile:upload_image",
            "receptionist_profile:delete_image",
        }
    ),
    "lab_access": frozenset({"lab:view", "notifications:view", "notifications:update"}),
    "lab_results": frozenset({"lab:update", "lab:upload_report"}),
    "lab_profile": frozenset(
        {
            "lab_technician_profile:view",
            "lab_technician_profile:update",
            "lab_technician_profile:upload_image",
            "lab_technician_profile:delete_image",
        }
    ),
    "nurse_access": frozenset(
        {
            "patients:view",
            "opd:view",
            "nurse_profile:view",
            "nurse_profile:update",
            "nurse_profile:upload_image",
            "nurse_profile:delete_image",
            "notifications:view",
            "notifications:update",
        }
    ),
    "nurse_clinical": frozenset(
        {
            "nurse_vitals:view",
            "nurse_vitals:create",
            "nurse_vitals:update",
            "nurse_notes:view",
            "nurse_notes:create",
            "nurse_notes:update",
            "nurse_medication:view",
            "nurse_medication:create",
            "nurse_medication:update",
        }
    ),
    "nurse_operations": frozenset(),
    "pharmacy_access": frozenset(
        {
            "prescriptions:view",
            "notifications:view",
            "notifications:update",
        }
    ),
    "pharmacy_dispense": frozenset({"prescriptions:dispense"}),
    "pharmacy_profile": frozenset(
        {
            "pharmacist_profile:view",
            "pharmacist_profile:update",
            "pharmacist_profile:upload_image",
            "pharmacist_profile:delete_image",
        }
    ),
}

ROLE_MODULE_LOCK_KEYS: dict[str, tuple[str, ...]] = {
    "doctor": ("doctor_access", "doctor_clinical", "doctor_profile"),
    "receptionist": ("receptionist_access", "receptionist_profile"),
    "lab_technician": ("lab_access", "lab_results", "lab_profile"),
    "nurse": ("nurse_access", "nurse_clinical", "nurse_operations"),
    "pharmacist": ("pharmacy_access", "pharmacy_dispense", "pharmacy_profile"),
}


def normalize_admin_edit(raw: Any) -> dict[str, bool]:
    out = dict(DEFAULT_ADMIN_EDIT)
    if isinstance(raw, dict):
        for key in DEFAULT_ADMIN_EDIT:
            if key in raw and raw[key] is not None:
                out[key] = bool(raw[key])
    return out


def merge_admin_edit_patch(current: dict[str, bool], patch: Optional[dict]) -> dict[str, bool]:
    merged = dict(current)
    if not isinstance(patch, dict):
        return merged
    for key, value in patch.items():
        if key in merged and value is not None:
            merged[key] = bool(value)
    return merged


def locked_permission_names(locks: dict[str, bool], role_name: str) -> frozenset[str]:
    names: set[str] = set()
    for lock_key in ROLE_MODULE_LOCK_KEYS.get((role_name or "").strip().lower(), ()):
        if not locks.get(lock_key, True):
            names.update(MODULE_CARD_PERMISSION_KEYS.get(lock_key, frozenset()))
    return frozenset(names)


def apply_module_locks_to_permission_ids(
    *,
    locks: dict[str, bool],
    role_name: str,
    current_permission_ids: Iterable[int],
    current_name_by_id: dict[int, str],
    requested_permission_ids: list[int],
    permission_id_by_name: dict[str, int],
) -> list[int]:
    """
    Preserve permission IDs that belong to locked module cards.
    Unlocked card permissions follow the request.
    """
    locked_names = locked_permission_names(locks, role_name)
    if not locked_names:
        return list(requested_permission_ids)

    current_ids = set(current_permission_ids)
    current_names = {
        current_name_by_id[pid]
        for pid in current_ids
        if pid in current_name_by_id
    }
    requested_names = {
        current_name_by_id.get(pid) or ""
        for pid in requested_permission_ids
    }
    # Prefer name lookup via id_by_name reverse for requested
    id_to_name = dict(current_name_by_id)
    for name, pid in permission_id_by_name.items():
        id_to_name[pid] = name
    requested_names = {id_to_name[pid] for pid in requested_permission_ids if pid in id_to_name}

    final_names: set[str] = set()
    # Start from requested unlocked names
    for name in requested_names:
        if name and name not in locked_names:
            final_names.add(name)
    # Force locked names to current role state
    for name in locked_names:
        if name in current_names:
            final_names.add(name)

    # Keep unrelated permissions (not in any module card for this role)
    all_module_names = set()
    for lock_key in ROLE_MODULE_LOCK_KEYS.get((role_name or "").strip().lower(), ()):
        all_module_names.update(MODULE_CARD_PERMISSION_KEYS.get(lock_key, frozenset()))
    for name in current_names:
        if name not in all_module_names:
            final_names.add(name)
    for name in requested_names:
        if name and name not in all_module_names:
            final_names.add(name)

    result: list[int] = []
    seen: set[int] = set()
    for name in sorted(final_names):
        pid = permission_id_by_name.get(name)
        if pid is not None and pid not in seen:
            seen.add(pid)
            result.append(pid)
    return result
