import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.lead_schema import BILLING_CYCLES, PLAN_NAMES
from Schemas.tenant_schema import TENANT_STATUSES, TRIAL_PERIODS


class RegisterFromLead(BaseModel):
    """Fields CRM does not collect. The rest is copied from the agreed lead."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=3, max_length=12)
    address: str = Field(..., min_length=1)
    pincode: str = Field(..., min_length=4, max_length=10)
    admin_password: str = Field(..., min_length=8)
    plan: str = Field(..., max_length=50)
    billing_cycle: str = Field(..., max_length=20)
    trial_period: str = Field("None", max_length=20)
    tenant_status: str = Field("Active", max_length=20)

    @field_validator("code")
    @classmethod
    def tenant_code(cls, value: str) -> str:
        text = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{3,12}", text):
            raise ValueError("Use 3–12 letters, numbers, or hyphens.")
        return text

    @field_validator("address", "pincode")
    @classmethod
    def strip_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("This field is required.")
        return text

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


class RegistrationOut(BaseModel):
    id: int
    hospital_name: str
    hospital_type: str
    city: str
    state: str | None = None
    hospital_email: str | None = None
    contact_person: str
    designation: str | None = None
    contact_phone: str
    contact_email: str | None = None
    plan: str | None = None
    billing_cycle: str | None = None
    source: str
    agreed_at: str | None = None
    agreed_by_name: str | None = None
    handover_note: str | None = None
    status: str
    hospital_id: int | None = None
    hospital_code: str | None = None
    registered_at: str | None = None
    registered_by_name: str | None = None
