"""CRM profile, password, and photo. The signed-in user can change only their own row."""
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from Models.crm_profile import CrmProfile
from Models.user import User
from Schemas.crm_profile_schema import CrmPasswordChange, CrmProfileOut, CrmProfileUpdate
from Services.auth_profile_image import to_profile_image_url
from hash import hash_password, verify_password

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _now():
    return datetime.now(IST)


def _upload_dir() -> Path:
    folder = Path(os.getenv("CRM_PROFILE_UPLOAD_DIR", "uploads/crm_image"))
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


def _load_crm(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.role_obj), joinedload(User.crm_profile))
        .filter(User.id == user_id)
        .first()
    )
    role = user.role_obj.name if user and user.role_obj else ""
    if user is None or role != "crm" or user.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only a CRM user can manage this profile")
    if user.crm_profile is None:
        user.crm_profile = CrmProfile(user_id=user.id)
        db.add(user.crm_profile)
        db.flush()
    return user


def _out(user: User) -> CrmProfileOut:
    profile = user.crm_profile
    return CrmProfileOut(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role_obj.name if user.role_obj else "crm",
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


def get_profile(db: Session, actor: User) -> CrmProfileOut:
    return _out(_load_crm(db, actor.id))


def update_profile(db: Session, actor: User, data: CrmProfileUpdate) -> CrmProfileOut:
    user = _load_crm(db, actor.id)
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for field in ("phone", "phone_code", "address", "city", "state", "postal_code"):
        if field in updates:
            setattr(user, field, updates[field])
    if "job_title" in updates:
        user.crm_profile.job_title = updates["job_title"]
    user.crm_profile.updated_at = _now()
    db.commit()
    return _out(_load_crm(db, actor.id))


def change_password(db: Session, actor: User, data: CrmPasswordChange) -> dict:
    user = _load_crm(db, actor.id)
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=422, detail="Choose a different password.")
    user.password = hash_password(data.new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return {"message": "Password updated. Sign in again."}


def upload_photo(db: Session, actor: User, file: UploadFile) -> CrmProfileOut:
    user = _load_crm(db, actor.id)
    profile = user.crm_profile
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
        logger.exception("Failed to save CRM photo for user %s", user.id)
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
            logger.warning("Could not remove previous CRM photo %s", old_path)
    return _out(_load_crm(db, actor.id))


def delete_photo(db: Session, actor: User) -> CrmProfileOut:
    user = _load_crm(db, actor.id)
    profile = user.crm_profile
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
            logger.warning("Could not remove CRM photo %s", path)
    return _out(_load_crm(db, actor.id))
