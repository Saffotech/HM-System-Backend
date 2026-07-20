from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from jose import JWTError
from database import get_db
from Models.user import User
from Models.role import Role
from jwt_token import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
        payload      = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # load user WITH role relationship
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    return user


def _permissions_for_user(user: User) -> list[str]:
    if not user.role_obj:
        return []
    return [p.name for p in (user.role_obj.permissions or [])]


# Checks permission against live role permissions (DB), with JWT as fallback.
# Live DB check means seed/role updates apply without waiting for token re-issue.
class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(
        self,
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db),
    ) -> bool:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")

            user = (
                db.query(User)
                .options(
                    joinedload(User.role_obj).joinedload(Role.permissions)
                )
                .filter(User.id == int(user_id))
                .first()
            )
            if not user:
                raise HTTPException(status_code=401, detail="Invalid token")
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is deactivated",
                )

            live_permissions = set(_permissions_for_user(user))
            token_permissions = set(payload.get("permissions") or [])
            permissions = live_permissions | token_permissions

            if self.required_permission not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {self.required_permission} required",
                )
            return True
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
