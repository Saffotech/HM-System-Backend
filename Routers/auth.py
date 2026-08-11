from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session, joinedload
from database import get_db
from Models.user import User
from Models.role import Role
from Schemas.schemas import RefreshTokenRequest, UserCreate, UserLogin
from hash import verify_password
from jwt_token import create_access_token, create_refresh_token, decode_refresh_token
from dependencies import PermissionChecker, get_current_user
from datetime import datetime
from zoneinfo import ZoneInfo
from Services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _permissions_for_user(user: User) -> list[str]:
    if not user.role_obj:
        return []
    return [p.name for p in (user.role_obj.permissions or [])]


def _issue_token_pair(user: User) -> dict:
    permissions = _permissions_for_user(user)
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role_obj.name if user.role_obj else "",
            "role_id": user.role_id,
            "permissions": permissions,
        }
    )
    refresh_token = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role_obj.name if user.role_obj else "",
        "permissions": permissions,
        "first_name": user.first_name,
        "user_id": user.id,
    }


@router.post("/register", status_code=201)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("users:create")),
):
    return auth_service.register_staff(db, data, current_user)


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .options(joinedload(User.role_obj).joinedload(Role.permissions))
        .filter(User.email == data.email)
        .first()
    )

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login = datetime.now(ZoneInfo("Asia/Kolkata"))
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    role_name = user.role_obj.name if user.role_obj else ""
    if role_name in {"admin", "super_admin"}:
        audit_service.log_event(
            db,
            actor=user,
            action="auth.login",
            resource_type="user",
            resource_id=user.id,
            summary=f"{role_name} logged in ({user.email})",
            details={"email": user.email, "role": role_name},
        )

    return _issue_token_pair(user)


@router.post("/refresh")
def refresh_tokens(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_refresh_token(data.refresh_token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = (
        db.query(User)
        .options(joinedload(User.role_obj).joinedload(Role.permissions))
        .filter(User.id == int(user_id), User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    tokens = _issue_token_pair(user)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"],
    }


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from Services.auth_profile_image import profile_image_url_for_user

    user = (
        db.query(User)
        .options(
            joinedload(User.role_obj).joinedload(Role.permissions),
            joinedload(User.doctor_profile),
            joinedload(User.nurse_profile),
            joinedload(User.receptionist_profile),
            joinedload(User.lab_technician_profile),
            joinedload(User.opd_billing_profile),
            joinedload(User.pharmacist_profile),
            joinedload(User.admin_profile),
            joinedload(User.super_admin_profile),
        )
        .filter(User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role_obj.name if user.role_obj else None,
        "role_id": user.role_id,
        "is_active": user.is_active,
        "created_at": str(user.created_at),
        "profile_image_url": profile_image_url_for_user(user),
        "permissions": _permissions_for_user(user),
    }
