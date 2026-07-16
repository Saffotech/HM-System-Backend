"""Nurse profile service — GET/PUT profile and image upload/delete."""
import logging
import os
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from Models.nurse_profile import NurseProfile
from Utils.profile_image import (
    delete_profile_image_file,
    remove_orphan_profile_image,
    save_profile_image_from_upload,
    to_profile_image_url,
)
from Utils.shift_time import format_shift_time
from Models.user import User
from Schemas.nurse_profile_schema import (
    AddressInfo,
    DepartmentInfo,
    EmergencyContactInfo,
    NurseProfileResponse,
    NurseProfileUpdate,
    RoleInfo,
    ShiftInfo,
)

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
NURSE_ROLE = "nurse"
NURSE_UPLOAD_DIR = os.getenv("NURSE_PROFILE_UPLOAD_DIR", "uploads/nurse_image")


def _now():
    return datetime.now(IST)


def _assert_nurse(user: User) -> None:
    role_name = user.role_obj.name if user.role_obj else None
    if role_name != NURSE_ROLE:
        raise HTTPException(
            status_code=403,
            detail="Only nurses can access this endpoint",
        )


def _normalize_languages(languages: Optional[List[str]]) -> List[str]:
    if languages is None:
        return []
    cleaned: List[str] = []
    seen = set()
    for raw in languages:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def compute_profile_completed(profile: NurseProfile) -> bool:
    return bool(
        profile.qualification
        and profile.experience_years is not None
        and profile.bio
    )


def compute_profile_completion_percentage(user: User, profile: NurseProfile) -> int:
    languages = profile.languages if isinstance(profile.languages, list) else []
    checks = [
        bool(user.phone),
        bool(user.phone_code),
        bool(user.address),
        bool(user.city),
        bool(user.state),
        user.date_of_birth is not None,
        user.gender is not None,
        bool(user.emergency_contact_name),
        bool(user.emergency_contact_phone),
        bool(profile.qualification),
        profile.experience_years is not None,
        bool(profile.bio),
        bool(languages),
        bool(profile.profile_image),
    ]
    if not checks:
        return 0
    return int(round(100 * sum(1 for ok in checks if ok) / len(checks)))


def _get_nurse_user(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.department),
            joinedload(User.nurse_profile),
        )
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_nurse(user)
    return user


def _get_profile_or_404(user: User) -> NurseProfile:
    profile = user.nurse_profile
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Nurse profile not found. Contact admin.",
        )
    return profile


def _to_response(user: User, profile: NurseProfile) -> NurseProfileResponse:
    languages = profile.languages if isinstance(profile.languages, list) else []

    department = None
    if user.department:
        department = DepartmentInfo(id=user.department.id, name=user.department.name)

    role = None
    if user.role_obj:
        role = RoleInfo(id=user.role_obj.id, name=user.role_obj.name)

    shift = None
    if profile.shift_name or profile.shift_start_time or profile.shift_end_time:
        shift = ShiftInfo(
            name=profile.shift_name,
            start_time=format_shift_time(profile.shift_start_time),
            end_time=format_shift_time(profile.shift_end_time),
        )

    return NurseProfileResponse(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        phone_code=user.phone_code,
        address=AddressInfo(
            line=user.address,
            city=user.city,
            state=user.state,
        ),
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        emergency_contact=EmergencyContactInfo(
            name=user.emergency_contact_name,
            phone=user.emergency_contact_phone,
        ),
        department=department,
        role=role,
        qualification=profile.qualification,
        registration_number=profile.registration_number,
        employee_id=profile.employee_id,
        experience_years=profile.experience_years,
        joining_date=profile.joining_date,
        bio=profile.bio,
        languages=languages,
        shift=shift,
        profile_image_url=to_profile_image_url(profile.profile_image),
        is_profile_completed=bool(profile.is_profile_completed),
        profile_completion_percentage=compute_profile_completion_percentage(
            user, profile
        ),
        is_active=bool(user.is_active),
        last_login=user.last_login,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def get_nurse_profile(db: Session, current_user: User) -> NurseProfileResponse:
    user = _get_nurse_user(db, current_user.id)
    profile = _get_profile_or_404(user)
    return _to_response(user, profile)


def update_nurse_profile(
    db: Session,
    current_user: User,
    data: NurseProfileUpdate,
) -> NurseProfileResponse:
    user = _get_nurse_user(db, current_user.id)
    profile = _get_profile_or_404(user)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    profile_fields = ("qualification", "experience_years", "bio")
    user_fields = (
        "phone",
        "phone_code",
        "date_of_birth",
        "gender",
    )

    for field in profile_fields:
        if field in updates:
            setattr(profile, field, updates[field])

    if "languages" in updates:
        profile.languages = _normalize_languages(updates["languages"])

    for field in user_fields:
        if field in updates:
            setattr(user, field, updates[field])

    if "address" in updates and updates["address"] is not None:
        address = updates["address"]
        if "line" in address:
            user.address = address["line"]
        if "city" in address:
            user.city = address["city"]
        if "state" in address:
            user.state = address["state"]

    if "emergency_contact" in updates and updates["emergency_contact"] is not None:
        contact = updates["emergency_contact"]
        if "name" in contact:
            user.emergency_contact_name = contact["name"]
        if "phone" in contact:
            user.emergency_contact_phone = contact["phone"]

    profile.is_profile_completed = compute_profile_completed(profile)
    profile.updated_at = _now()

    db.commit()
    user = _get_nurse_user(db, current_user.id)
    profile = _get_profile_or_404(user)

    logger.info("Nurse %s updated profile", current_user.id)
    return _to_response(user, profile)


def upload_profile_image(
    db: Session,
    current_user: User,
    file: UploadFile,
) -> dict:
    user = _get_nurse_user(db, current_user.id)
    profile = _get_profile_or_404(user)

    old_stored_path = profile.profile_image
    stored_path, absolute_path = save_profile_image_from_upload(
        file, NURSE_UPLOAD_DIR
    )

    profile.profile_image = stored_path
    profile.updated_at = _now()

    try:
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        remove_orphan_profile_image(absolute_path)
        raise

    delete_profile_image_file(NURSE_UPLOAD_DIR, old_stored_path)

    logger.info("Nurse %s uploaded profile image", current_user.id)
    return {
        "message": "Profile image uploaded successfully",
        "profile_image_url": to_profile_image_url(profile.profile_image),
    }


def delete_profile_image(db: Session, current_user: User) -> dict:
    user = _get_nurse_user(db, current_user.id)
    profile = _get_profile_or_404(user)

    if not profile.profile_image:
        raise HTTPException(status_code=404, detail="No profile image to delete")

    old_stored_path = profile.profile_image
    profile.profile_image = None
    profile.updated_at = _now()
    db.commit()

    delete_profile_image_file(NURSE_UPLOAD_DIR, old_stored_path)

    logger.info("Nurse %s deleted profile image", current_user.id)
    return {
        "message": "Profile image deleted successfully",
        "profile_image_url": None,
    }


def create_empty_nurse_profile(
    db: Session,
    user_id: int,
    *,
    registration_number: Optional[str] = None,
) -> NurseProfile:
    """Create empty nurse_profiles row (used during registration). Caller commits."""
    profile = NurseProfile(
        user_id=user_id,
        registration_number=registration_number,
        languages=[],
        is_profile_completed=False,
    )
    db.add(profile)
    return profile
