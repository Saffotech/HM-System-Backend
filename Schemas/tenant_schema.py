from pydantic import BaseModel, EmailStr, Field


class TenantRegisterRequest(BaseModel):
    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=50)
    hospital_type: str = Field(..., max_length=50)
    email: EmailStr
    phone: str = Field(..., max_length=30)
    address: str
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    pincode: str = Field(..., max_length=20)
    admin_full_name: str = Field(..., max_length=200)
    admin_email: EmailStr
    admin_phone: str = Field(..., max_length=30)
    admin_password: str = Field(..., min_length=8)


class TenantRegisterResponse(BaseModel):
    tenant_id: int
    name: str
    code: str
    hospital_type: str
    admin_user_id: int
    admin_email: str
