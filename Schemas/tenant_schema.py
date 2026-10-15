from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from Schemas.lead_schema import BILLING_CYCLES, PLAN_NAMES

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
        if text not in PLAN_NAMES:
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
