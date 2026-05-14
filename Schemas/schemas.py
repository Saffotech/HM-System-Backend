from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: Optional[str] = None
    email: EmailStr
    password: str = Field(..., min_length=8)
    role:str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
