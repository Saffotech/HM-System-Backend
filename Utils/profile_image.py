"""Shared profile image upload helpers — validation, paths, save/delete."""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

_JPEG_SIG = b"\xff\xd8\xff"
_PNG_SIG = b"\x89PNG"
_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"


def get_upload_dir(upload_dir: str) -> Path:
    path = Path(upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def stored_image_path(upload_dir: str, filename: str) -> str:
    absolute = (get_upload_dir(upload_dir) / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def resolve_image_path(upload_dir: str, stored_path: str) -> Path:
    root = get_upload_dir(upload_dir).resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Invalid profile image path")
    return candidate


def to_profile_image_url(stored_path: Optional[str]) -> Optional[str]:
    """Map DB filesystem path to a public URL for the frontend."""
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def _detect_image_type(data: bytes) -> Optional[str]:
    """Return canonical extension (.jpg, .png, .webp) or None."""
    if len(data) >= 3 and data[:3] == _JPEG_SIG:
        return ".jpg"
    if len(data) >= 4 and data[:4] == _PNG_SIG:
        return ".png"
    if len(data) >= 12 and data[:4] == _WEBP_RIFF and data[8:12] == _WEBP_MARKER:
        return ".webp"
    return None


def _extension_matches_detected_type(extension: str, detected: str) -> bool:
    if detected == ".jpg":
        return extension in {".jpg", ".jpeg"}
    return extension == detected


def validate_profile_image_upload(file: UploadFile) -> tuple[bytes, str]:
    """
    Validate filename, extension, size, and magic bytes.
    Returns (file_bytes, extension_with_dot).
    """
    if not file.filename:
        raise HTTPException(
            status_code=400, detail="Uploaded file must include a filename"
        )

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

    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB")

    detected = _detect_image_type(content)
    if detected is None:
        raise HTTPException(status_code=400, detail="File content is not a valid image")
    if not _extension_matches_detected_type(extension, detected):
        raise HTTPException(
            status_code=400,
            detail="File extension does not match image content",
        )

    return content, extension


def save_profile_image_bytes(
    content: bytes, upload_dir: str, extension: str
) -> tuple[str, Path]:
    """Write validated bytes to disk. Returns (stored_path_for_db, absolute_path)."""
    unique_name = f"{uuid.uuid4()}{extension}"
    stored_path = stored_image_path(upload_dir, unique_name)
    absolute_path = get_upload_dir(upload_dir) / unique_name
    try:
        absolute_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save file") from exc
    return stored_path, absolute_path


def save_profile_image_from_upload(
    file: UploadFile, upload_dir: str
) -> tuple[str, Path]:
    """Validate upload and save to disk. Returns (stored_path_for_db, absolute_path)."""
    content, extension = validate_profile_image_upload(file)
    return save_profile_image_bytes(content, upload_dir, extension)


def remove_orphan_profile_image(absolute_path: Path) -> None:
    """Remove a newly saved file when the DB transaction fails."""
    if absolute_path.exists():
        try:
            absolute_path.unlink()
        except OSError:
            logger.warning("Could not remove orphaned profile image %s", absolute_path)


def delete_profile_image_file(upload_dir: str, stored_path: Optional[str]) -> None:
    """Delete an existing profile image from disk (ignores missing/invalid paths)."""
    if not stored_path:
        return
    try:
        path = resolve_image_path(upload_dir, stored_path)
    except HTTPException:
        return
    if path.exists():
        try:
            path.unlink()
        except OSError:
            logger.warning("Could not remove profile image file %s", path)
