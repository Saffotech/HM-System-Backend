"""Private legal document storage. Not a malware scanner."""
import os
from pathlib import Path
from uuid import uuid4

from config import settings


class StorageError(Exception):
    pass


def is_blocked_public_path(path: str) -> bool:
    from urllib.parse import unquote
    normalized = unquote(path or "").replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if ".." in parts:
        return True
    collapsed = "/".join(parts).lower()
    return collapsed == "legal_documents" or collapsed.startswith("legal_documents/")


def private_root() -> Path:
    folder = Path(settings.LEGAL_PRIVATE_UPLOAD_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass
    return folder.resolve()


def _allowed_roots() -> list[Path]:
    roots = [private_root()]
    legacy = Path("uploads/legal_documents")
    if legacy.exists():
        roots.append(legacy.resolve())
    return roots


def save_private(case_id: int, suffix: str, content: bytes) -> Path:
    root = private_root()
    destination = (root / f"{case_id}-{uuid4().hex}{suffix}").resolve()
    if root not in destination.parents:
        raise StorageError("Refusing to write outside private storage")
    destination.write_bytes(content)
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return destination


def resolve_existing(stored_path: str) -> Path:
    candidate = Path(stored_path)
    if candidate.is_symlink():
        raise StorageError("Refusing a symbolic link")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise StorageError("File not found")
    for root in _allowed_roots():
        if resolved == root or root in resolved.parents:
            return resolved
    raise StorageError("Path is outside legal storage")


def delete_if_exists(stored_path: str) -> None:
    try:
        path = resolve_existing(stored_path)
    except StorageError:
        return
    path.unlink(missing_ok=True)
