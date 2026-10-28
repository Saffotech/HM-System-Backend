from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from Schemas.lead_schema import BILLING_CYCLES

TRIAL_PERIODS = ("None", "14 days", "30 days", "60 days")
TENANT_STATUSES = ("Active", "Trial", "Suspended")


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
    plan: str = Field(..., max_length=50)
    billing_cycle: str = Field(..., max_length=20)
    trial_period: str = Field("None", max_length=20)
    tenant_status: str = Field("Active", max_length=20)

    @field_validator("plan")
    @classmethod
    def known_plan(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Choose a subscription plan.")
        return text

    @field_validator("billing_cycle")
    @classmethod
    def known_cycle(cls, value: str) -> str:
        text = value.strip()
        if text not in BILLING_CYCLES:
            raise ValueError("Choose a billing cycle.")
        return text

    @field_validator("trial_period")
    @classmethod
    def known_trial(cls, value: str) -> str:
        text = value.strip()
        if text not in TRIAL_PERIODS:
            raise ValueError("Choose a trial period.")
        return text

    @field_validator("tenant_status")
    @classmethod
    def known_status(cls, value: str) -> str:
        text = value.strip()
        if text not in TENANT_STATUSES:
            raise ValueError("Choose a tenant status.")
        return text


class TenantActiveUpdate(BaseModel):
    is_active: bool


class TenantUpdate(BaseModel):
    """Correct a hospital record. Identity, status, and invoices stay untouched."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=200)
    address: str | None = None
    phone: str | None = Field(None, max_length=30)
    plan: str | None = Field(None, max_length=50)
    billing_cycle: str | None = Field(None, max_length=20)
    subscription_renews_on: date | None = None
    subscription_amount: int | None = Field(None, ge=1, le=10_000_000)

    @field_validator("name", "address", "phone", mode="before")
    @classmethod
    def required_text(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("This field cannot be empty.")
        return text

    @field_validator("plan")
    @classmethod
    def known_plan_update(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Choose a subscription plan.")
        return text

    @field_validator("billing_cycle")
    @classmethod
    def known_cycle_update(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if text not in BILLING_CYCLES:
            raise ValueError("Choose a billing cycle.")
        return text

    @field_validator("subscription_renews_on")
    @classmethod
    def renewal_window(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value.year < 2000 or value.year > date.today().year + 5:
            raise ValueError("Choose a renewal date within the next five years.")
        return value


class TenantSummary(BaseModel):
    tenant_id: int
    name: str
    code: str
    hospital_type: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    admin_user_id: int | None = None
    admin_email: str | None = None
    plan: str
    billing_cycle: str
    trial_period: str
    tenant_status: str
    subscription_status: str
    is_active: bool
    subscription_started_on: date
    subscription_renews_on: date
    subscription_amount: int | None = None
    created_at: datetime


class TenantRegisterResponse(BaseModel):
    tenant_id: int
    name: str
    code: str
    hospital_type: str
    admin_user_id: int
    admin_email: str
    plan: str
    billing_cycle: str
    trial_period: str
    tenant_status: str
    subscription_status: str
    is_active: bool
    subscription_started_on: date
    subscription_renews_on: date
