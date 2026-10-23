"""Accountant profile, password, and photo. The signed-in user can change only their own row."""
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from Models.accountant_profile import AccountantProfile
from Models.user import User
from Schemas.accountant_profile_schema import (
    AccountantPasswordChange,
    AccountantProfileOut,
    AccountantProfileUpdate,
)
from Services.auth_profile_image import to_profile_image_url
from hash import hash_password, verify_password

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _now():
    return datetime.now(IST)


def _upload_dir() -> Path:
    folder = Path(os.getenv("ACCOUNTANT_PROFILE_UPLOAD_DIR", "uploads/accountant_image"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _stored_path(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def _resolve(stored_path: str) -> Path:
    upload_dir = _upload_dir().resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if upload_dir not in candidate.parents and candidate != upload_dir:
        raise HTTPException(status_code=400, detail="Invalid profile image path")
    return candidate


def _load_accountant(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.role_obj), joinedload(User.accountant_profile))
        .filter(User.id == user_id)
        .first()
    )
    role = user.role_obj.name if user and user.role_obj else ""
    if user is None or role != "accountant" or user.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only an accountant can manage this profile")
    if user.accountant_profile is None:
        user.accountant_profile = AccountantProfile(user_id=user.id)
        db.add(user.accountant_profile)
        db.flush()
    return user


def _out(user: User) -> AccountantProfileOut:
    profile = user.accountant_profile
    return AccountantProfileOut(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role_obj.name if user.role_obj else "accountant",
        phone=user.phone,
        phone_code=user.phone_code,
        address=user.address,
        city=user.city,
        state=user.state,
        postal_code=user.postal_code,
        job_title=profile.job_title if profile else None,
        profile_image_url=to_profile_image_url(profile.profile_image) if profile else None,
        is_active=bool(user.is_active),
        created_at=user.created_at.date() if user.created_at else None,
    )


def get_profile(db: Session, actor: User) -> AccountantProfileOut:
    return _out(_load_accountant(db, actor.id))


def update_profile(db: Session, actor: User, data: AccountantProfileUpdate) -> AccountantProfileOut:
    user = _load_accountant(db, actor.id)
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for field in ("phone", "phone_code", "address", "city", "state", "postal_code"):
        if field in updates:
            setattr(user, field, updates[field])
    if "job_title" in updates:
        user.accountant_profile.job_title = updates["job_title"]
    user.accountant_profile.updated_at = _now()
    db.commit()
    return _out(_load_accountant(db, actor.id))


def change_password(db: Session, actor: User, data: AccountantPasswordChange) -> dict:
    user = _load_accountant(db, actor.id)
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=422, detail="Choose a different password.")
    user.password = hash_password(data.new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return {"message": "Password updated. Sign in again."}


def upload_photo(db: Session, actor: User, file: UploadFile) -> AccountantProfileOut:
    user = _load_accountant(db, actor.id)
    profile = user.accountant_profile
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
            old_path = _resolve(profile.profile_image)
        except HTTPException:
            old_path = None
    name = f"{uuid.uuid4()}{extension}"
    absolute = _upload_dir() / name
    try:
        with open(absolute, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        logger.exception("Failed to save accountant photo for user %s", user.id)
        raise HTTPException(status_code=500, detail="Failed to save file") from exc
    profile.profile_image = _stored_path(name)
    profile.updated_at = _now()
    try:
        db.commit()
    except Exception:
        db.rollback()
        if absolute.exists():
            absolute.unlink(missing_ok=True)
        raise
    if old_path and old_path.exists() and old_path != absolute:
        try:
            old_path.unlink()
        except OSError:
            logger.warning("Could not remove previous accountant photo %s", old_path)
    return _out(_load_accountant(db, actor.id))


def delete_photo(db: Session, actor: User) -> AccountantProfileOut:
    user = _load_accountant(db, actor.id)
    profile = user.accountant_profile
    if not profile.profile_image:
        raise HTTPException(status_code=404, detail="No profile photo to remove")
    try:
        path = _resolve(profile.profile_image)
    except HTTPException:
        path = None
    profile.profile_image = None
    profile.updated_at = _now()
    db.commit()
    if path and path.exists():
        try:
            path.unlink()
        except OSError:
            logger.warning("Could not remove accountant photo %s", path)
    return _out(_load_accountant(db, actor.id))
