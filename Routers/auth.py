from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.user import User
from Schemas.schemas import UserCreate, UserLogin
from hash import verify_password
from jwt_token import create_access_token
from dependencies import PermissionChecker, get_current_user
from datetime import datetime
from zoneinfo import ZoneInfo
from Services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])



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
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # load permissions from role
    permissions = []
    if user.role_obj:
        permissions = [p.name for p in user.role_obj.permissions]

    # update last_login and login_count
    user.last_login  = datetime.now(ZoneInfo("Asia/Kolkata"))
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

    token = create_access_token({
        "sub":         str(user.id),
        "role":        user.role_obj.name if user.role_obj else "",
        "role_id":     user.role_id,
        "permissions": permissions
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role_obj.name if user.role_obj else "",
        "permissions":  permissions,
        "first_name":   user.first_name,
        "user_id":      user.id
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id":    current_user.id,
        "email":      current_user.email,
        "first_name": current_user.first_name,
        "last_name":  current_user.last_name,
        "role":       current_user.role_obj.name if current_user.role_obj else None,
        "role_id":    current_user.role_id,
        "is_active":  current_user.is_active,
        "created_at": str(current_user.created_at)
    }