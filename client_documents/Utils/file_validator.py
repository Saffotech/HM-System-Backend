"""Extension, MIME, and signature checks. Not a malware scanner."""
from pathlib import PurePath

SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".webp": [b"RIFF"],
}
MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class FileValidationError(Exception):
    pass


def sanitize_filename(name: str | None) -> str:
    base = PurePath((name or "").replace("\\", "/")).name.strip()
    return base or "document"


def validate_bytes(content: bytes, filename: str, allowed: set[str], max_bytes: int) -> tuple[str, str]:
    if not content:
        raise FileValidationError("The file is empty.")
    if len(content) > max_bytes:
        raise FileValidationError("The file is too large.")
    suffix = PurePath(filename).suffix.lower()
    if suffix not in allowed:
        raise FileValidationError("This file type is not allowed.")
    magic = SIGNATURES.get(suffix, [])
    if suffix == ".webp":
        if not (content.startswith(b"RIFF") and b"WEBP" in content[:16]):
            raise FileValidationError("The file content does not match its extension.")
    elif magic and not any(content.startswith(sig) for sig in magic):
        raise FileValidationError("The file content does not match its extension.")
    return suffix, MIME.get(suffix, "application/octet-stream")
