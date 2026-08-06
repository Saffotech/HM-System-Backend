"""IPD staff profile service — GET/PUT profile and image upload/delete."""
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from Models.ipd_profile import IpdProfile
from Models.user import User
from Schemas.ipd_profile_schema import (
    AddressInfo,
    DepartmentInfo,
    EmergencyContactInfo,
    IpdProfileResponse,
    IpdProfileUpdate,
    RoleInfo,
    ShiftInfo,
)

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
IPD_ROLE = "ipd"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _now():
    return datetime.now(IST)


def _get_upload_dir() -> Path:
    upload_dir = Path(os.getenv("IPD_PROFILE_UPLOAD_DIR", "uploads/ipd_image"))
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


def to_profile_image_url(stored: Optional[str]) -> Optional[str]:
    if not stored:
        return None
    if stored.startswith("http"):
        return stored
    return f"/{stored.lstrip('/')}"


def create_empty_ipd_profile(db: Session, user_id: int) -> IpdProfile:
    existing = db.query(IpdProfile).filter(IpdProfile.user_id == user_id).first()
    if existing:
        return existing
    profile = IpdProfile(user_id=user_id, languages=[])
    db.add(profile)
    db.flush()
    return profile


def _assert_ipd(user: User) -> None:
    role_name = user.role_obj.name if user.role_obj else None
    if role_name != IPD_ROLE:
        raise HTTPException(status_code=403, detail="Only IPD staff can access this endpoint")


def _normalize_languages(languages: Optional[List[str]]) -> List[str]:
    if languages is None:
        return []
    cleaned: List[str] = []
    for item in languages:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _get_ipd_user(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.role_obj), joinedload(User.department), joinedload(User.ipd_profile))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_ipd(user)
    if not user.ipd_profile:
        create_empty_ipd_profile(db, user.id)
        db.commit()
        user = (
            db.query(User)
            .options(joinedload(User.role_obj), joinedload(User.department), joinedload(User.ipd_profile))
            .filter(User.id == user_id)
            .first()
        )
    return user


def _to_response(user: User, profile: IpdProfile) -> IpdProfileResponse:
    role = user.role_obj
    dept = user.department
    return IpdProfileResponse(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        phone_code=getattr(user, "phone_code", None),
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        qualification=profile.qualification,
        employee_id=profile.employee_id,
        experience_years=profile.experience_years,
        joining_date=profile.joining_date,
        bio=profile.bio,
        languages=list(profile.languages or []),
        profile_image_url=to_profile_image_url(profile.profile_image),
        is_profile_completed=bool(profile.is_profile_completed),
        role=RoleInfo(id=role.id, name=role.name) if role else None,
        department=DepartmentInfo(id=dept.id, name=dept.name) if dept else None,
        shift=ShiftInfo(
            name=profile.shift_name,
            start_time=profile.shift_start_time,
            end_time=profile.shift_end_time,
        ),
        address=AddressInfo(
            line1=user.address,
            city=getattr(user, "city", None),
            state=user.state,
            pincode=getattr(user, "pincode", None),
        ),
        emergency_contact=EmergencyContactInfo(
            name=getattr(user, "emergency_contact_name", None),
            phone=getattr(user, "emergency_contact_phone", None),
            relation=getattr(user, "emergency_contact_relation", None),
        ),
        updated_at=profile.updated_at,
    )


def get_ipd_profile(db: Session, current_user: User) -> IpdProfileResponse:
    user = _get_ipd_user(db, current_user.id)
    return _to_response(user, user.ipd_profile)


def update_ipd_profile(
    db: Session, current_user: User, data: IpdProfileUpdate
) -> IpdProfileResponse:
    user = _get_ipd_user(db, current_user.id)
    profile = user.ipd_profile
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field in ("qualification", "experience_years", "bio"):
        if field in updates:
            setattr(profile, field, updates[field])
    if "languages" in updates:
        profile.languages = _normalize_languages(updates["languages"])
    for field in ("phone", "phone_code", "date_of_birth", "gender"):
        if field in updates and hasattr(user, field):
            setattr(user, field, updates[field])

    profile.is_profile_completed = bool(
        profile.qualification or profile.bio or (profile.languages or [])
    )
    profile.updated_at = _now()
    db.commit()
    user = _get_ipd_user(db, current_user.id)
    return _to_response(user, user.ipd_profile)


def upload_profile_image(db: Session, current_user: User, file: UploadFile) -> dict:
    user = _get_ipd_user(db, current_user.id)
    profile = user.ipd_profile
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, PNG and WEBP images are allowed")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB")

    old_path = None
    if profile.profile_image:
        try:
            old_path = _resolve_image_path(profile.profile_image)
        except HTTPException:
            old_path = None

    filename = f"{uuid.uuid4().hex}{extension}"
    dest = _get_upload_dir() / filename
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    profile.profile_image = _stored_image_path(filename)
    profile.updated_at = _now()
    db.commit()

    if old_path and old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            logger.warning("Could not delete old IPD profile image %s", old_path)

    return {
        "profile_image_url": to_profile_image_url(profile.profile_image),
        "message": "Profile image uploaded",
    }


def delete_profile_image(db: Session, current_user: User) -> dict:
    user = _get_ipd_user(db, current_user.id)
    profile = user.ipd_profile
    if profile.profile_image:
        try:
            path = _resolve_image_path(profile.profile_image)
            if path.exists():
                path.unlink()
        except HTTPException:
            pass
        except OSError:
            logger.warning("Could not delete IPD profile image")
    profile.profile_image = None
    profile.updated_at = _now()
    db.commit()
    return {"profile_image_url": None, "message": "Profile image deleted"}
