"""Resolve staff profile image path for the authenticated user's role."""
from typing import Optional

from Models.user import User


def to_profile_image_url(stored_path: Optional[str]) -> Optional[str]:
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def profile_image_url_for_user(user: User) -> Optional[str]:
    """Return public /uploads/... URL from the role-specific profile row, if any."""
    role_name = user.role_obj.name if user.role_obj else None
    profile = None

    if role_name == "doctor":
        profile = user.doctor_profile
    elif role_name == "nurse":
        profile = user.nurse_profile
    elif role_name == "receptionist":
        profile = user.receptionist_profile
    elif role_name == "lab_technician":
        profile = user.lab_technician_profile
    elif role_name == "opd_billing":
        profile = user.opd_billing_profile
    elif role_name == "pharmacist":
        profile = user.pharmacist_profile
    elif role_name == "admin":
        profile = user.admin_profile
    elif role_name == "super_admin":
        profile = user.super_admin_profile

    if not profile:
        return None
    return to_profile_image_url(getattr(profile, "profile_image", None))
