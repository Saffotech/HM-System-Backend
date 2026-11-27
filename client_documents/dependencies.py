import hashlib

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import settings
from database import get_db

_bearer = HTTPBearer(auto_error=False)


def require_client_documents_enabled() -> None:
    if not settings.CLIENT_DOCUMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Client document requests are disabled.")


def upload_token_hash(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> tuple[str, Session]:
    require_client_documents_enabled()
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Upload token required")
    digest = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    return digest, db
