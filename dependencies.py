from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from database import get_db
from Models.user import User
from jwt_token import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ─────────────────────────────────────────
# get_current_user — reads JWT from every request
# ─────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        role: str    = payload.get("role")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support."
        )
    return user


# ─────────────────────────────────────────
# get_current_user_payload — returns raw dict
# use this when you only need user_id + role
# ─────────────────────────────────────────
def get_current_user_payload(
    token: str = Depends(oauth2_scheme)
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        role: str    = payload.get("role")
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id, "role": role}
    except JWTError:
        raise credentials_exception


# ─────────────────────────────────────────
# PermissionChecker — role based access
# usage: Depends(PermissionChecker("admin"))
# ─────────────────────────────────────────
class PermissionChecker:
    def __init__(self, required_role: str):
        self.required_role = required_role

    def __call__(
        self,
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role != self.required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {self.required_role}"
            )
        return current_user