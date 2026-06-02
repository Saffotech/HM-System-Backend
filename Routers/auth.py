from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.user import User
from Schemas.schemas import UserCreate,UserLogin
from hash import hash_password, verify_password
from jwt_token import create_access_token
from dependencies import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime
from zoneinfo import ZoneInfo
from Models.role import Role  # ← add this import

router = APIRouter(prefix="/auth",tags=["Auth"])

@router.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    # check duplicate email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # check role exists  ← uses role_id now
    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role with id {data.role_id} not found")

    # create user
    new_user = User(
        first_name = data.first_name,
        last_name  = data.last_name,
        email      = data.email,
        password   = hash_password(data.password),
        role_id    = data.role_id,   # ← role_id not role
        department_id = data.department_id,  # ← add
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Staff registered successfully",
        "user_id": new_user.id,
        "email":   new_user.email,
        "role":    role.name
    }

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