from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountantProfileUpdate(BaseModel):
    """Fields an accountant may change. Role, email, and status are not accepted."""

    model_config = ConfigDict(extra="forbid")

    phone: str | None = Field(None, max_length=20)
    phone_code: str | None = Field(None, max_length=10)
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    job_title: str | None = Field(None, max_length=120)

    @field_validator("phone", "phone_code", "address", "city", "state", "postal_code", "job_title", mode="before")
    @classmethod
    def blank(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class AccountantPasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_shape(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Include at least one letter and one number.")
        return value


class AccountantProfileOut(BaseModel):
    user_id: int
    first_name: str
    last_name: str | None = None
    email: str
    role: str
    phone: str | None = None
    phone_code: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    job_title: str | None = None
    profile_image_url: str | None = None
    is_active: bool
    created_at: date | None = None
