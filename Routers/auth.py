from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.user import User
from Schemas.schemas import UserCreate,UserLogin
from hash import hash_password, verify_password
from jwt_token import create_access_token
from dependencies import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
router = APIRouter(prefix="/auth",tags=["Auth"])

@router.post("/register",status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        first_name = data.first_name,
        last_name = data.last_name,
        email = data.email,
        password = hash_password(data.password),
        role = data.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return{
        "message": "Staff registered successfully",
        "user_id": new_user.id,
        "email": new_user.email,
        "role":new_user.role
    }

@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role
    }

# add this route at the bottom
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id":    current_user.id,
        "email":      current_user.email,
        "first_name": current_user.first_name,
        "last_name":  current_user.last_name,
        "role":       current_user.role,
        "is_active":  current_user.is_active
    }