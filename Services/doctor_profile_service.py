"""Doctor profile service — GET/PUT profile and image upload/delete."""
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from Models.doctor_profile import DoctorProfile
from Models.user import User
from Schemas.doctor_profile_schema import DoctorProfileResponse, DoctorProfileUpdate

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
DOCTOR_ROLE = "doctor"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _now():
    return datetime.now(IST)


def _get_upload_dir() -> Path:
    upload_dir = Path(os.getenv("DOCTOR_PROFILE_UPLOAD_DIR", "uploads/doctor_image"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _stored_image_path(filename: str) -> str:
    absolute = (_get_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def _resolve_image_path(stored_path: str) -> Path:
    upload_dir = _get_upload_dir().resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if upload_dir not in candidate.parents and candidate != upload_dir:
        raise HTTPException(status_code=400, detail="Invalid profile image path")
    return candidate


def _assert_doctor(user: User) -> None:
    role_name = user.role_obj.name if user.role_obj else None
    if role_name != DOCTOR_ROLE:
        raise HTTPException(
            status_code=403,
            detail="Only doctors can access this endpoint",
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


def to_profile_image_url(stored_path: Optional[str]) -> Optional[str]:
    """Map DB filesystem path to a public URL for the frontend."""
    if not stored_path:
        return None
    # DB: uploads/doctor_image/uuid.jpg  →  URL: /uploads/doctor_image/uuid.jpg
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def compute_profile_completed(profile: DoctorProfile) -> bool:
    return bool(
        profile.qualification
        and profile.experience_years is not None
        and profile.bio
    )


def _get_doctor_user(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.department),
            joinedload(User.doctor_profile),
        )
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_doctor(user)
    return user


def _get_profile_or_404(user: User) -> DoctorProfile:
    profile = user.doctor_profile
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Doctor profile not found. Contact admin.",
        )
    return profile


def _to_response(user: User, profile: DoctorProfile) -> DoctorProfileResponse:
    languages = profile.languages if isinstance(profile.languages, list) else []
    return DoctorProfileResponse(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        address=user.address,
        city=user.city,
        state=user.state,
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        emergency_contact_phone=user.emergency_contact_phone,
        is_active=bool(user.is_active),
        department=user.department.name if user.department else None,
        specialization=user.specialization,
        qualification=profile.qualification,
        medical_license_number=profile.medical_license_number,
        experience_years=profile.experience_years,
        consultation_fee=profile.consultation_fee,
        bio=profile.bio,
        languages=languages,
        profile_image_url=to_profile_image_url(profile.profile_image),
        is_profile_completed=bool(profile.is_profile_completed),
    )


def get_doctor_profile(db: Session, current_user: User) -> DoctorProfileResponse:
    user = _get_doctor_user(db, current_user.id)
    profile = _get_profile_or_404(user)
    return _to_response(user, profile)


def update_doctor_profile(
    db: Session,
    current_user: User,
    data: DoctorProfileUpdate,
) -> DoctorProfileResponse:
    user = _get_doctor_user(db, current_user.id)
    profile = _get_profile_or_404(user)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    profile_fields = ("qualification", "experience_years", "bio")
    user_fields = (
        "phone",
        "address",
        "city",
        "state",
        "date_of_birth",
        "gender",
        "emergency_contact_phone",
    )

    for field in profile_fields:
        if field in updates:
            setattr(profile, field, updates[field])

    if "languages" in updates:
        profile.languages = _normalize_languages(updates["languages"])

    for field in user_fields:
        if field in updates:
            setattr(user, field, updates[field])

    profile.is_profile_completed = compute_profile_completed(profile)
    profile.updated_at = _now()

    db.commit()
    db.refresh(user)
    db.refresh(profile)

    logger.info("Doctor %s updated profile", current_user.id)
    return _to_response(user, profile)


def upload_profile_image(
    db: Session,
    current_user: User,
    file: UploadFile,
) -> dict:
    user = _get_doctor_user(db, current_user.id)
    profile = _get_profile_or_404(user)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG and WEBP images are allowed",
        )

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB")

    old_file_path = None
    if profile.profile_image:
        try:
            old_file_path = _resolve_image_path(profile.profile_image)
        except HTTPException:
            old_file_path = None

    unique_name = f"{uuid.uuid4()}{extension}"
    stored_path = _stored_image_path(unique_name)
    absolute_path = _get_upload_dir() / unique_name

    try:
        with open(absolute_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        logger.exception("Failed to save profile image for doctor %s", current_user.id)
        raise HTTPException(status_code=500, detail="Failed to save file") from exc

    profile.profile_image = stored_path
    profile.updated_at = _now()

    try:
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        if absolute_path.exists():
            try:
                absolute_path.unlink()
            except OSError:
                logger.warning("Could not remove orphaned profile image %s", absolute_path)
        raise

    if old_file_path and old_file_path.exists():
        try:
            old_file_path.unlink()
        except OSError:
            logger.warning("Could not remove old profile image %s", old_file_path)

    logger.info("Doctor %s uploaded profile image", current_user.id)
    return {
        "message": "Profile image uploaded successfully",
        "profile_image_url": to_profile_image_url(profile.profile_image),
    }


def delete_profile_image(db: Session, current_user: User) -> dict:
    user = _get_doctor_user(db, current_user.id)
    profile = _get_profile_or_404(user)

    if not profile.profile_image:
        raise HTTPException(status_code=404, detail="No profile image to delete")

    old_path = None
    try:
        old_path = _resolve_image_path(profile.profile_image)
    except HTTPException:
        old_path = None

    profile.profile_image = None
    profile.updated_at = _now()
    db.commit()

    if old_path and old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            logger.warning("Could not remove profile image file %s", old_path)

    logger.info("Doctor %s deleted profile image", current_user.id)
    return {
        "message": "Profile image deleted successfully",
        "profile_image_url": None,
    }


def create_empty_doctor_profile(
    db: Session,
    user_id: int,
    *,
    medical_license_number: Optional[str] = None,
    consultation_fee: Optional[float] = None,
) -> DoctorProfile:
    """Create empty doctor_profiles row (used during registration). Caller commits."""
    profile = DoctorProfile(
        user_id=user_id,
        medical_license_number=medical_license_number,
        consultation_fee=consultation_fee,
        languages=[],
        is_profile_completed=False,
    )
    db.add(profile)
    return profile
