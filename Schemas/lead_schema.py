import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

HOSPITAL_TYPES = (
    "Multi-specialty",
    "General",
    "Specialty",
    "Children's",
    "Diagnostic",
    "Teaching",
)
LEAD_SOURCES = (
    "Phone enquiry",
    "WhatsApp",
    "Referral",
    "Email",
    "Website",
    "Campaign",
    "Other",
)
PRIORITIES = ("High", "Medium", "Low")
PLAN_NAMES = ("Starter", "Professional", "Enterprise")
BILLING_CYCLES = ("Monthly", "Annual")
CONTACT_METHODS = ("Phone call", "Email", "WhatsApp", "Video meeting", "Site visit")
CONTACT_OUTCOMES = ("interested", "callback", "agreed", "not-interested")
CLOSE_REASONS = (
    "Not interested",
    "Budget constraints",
    "Chose another vendor",
    "Unreachable",
    "Duplicate request",
)
OPEN_STATUSES = ("New", "Contacted")


def _blank(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_phone(value: str) -> str:
    text = value.strip()
    count = sum(ch.isdigit() for ch in text)
    if not re.fullmatch(r"[+]?\d[\d\s()-]*", text) or not 10 <= count <= 15:
        raise ValueError("Enter a valid phone number (10–15 digits).")
    return text


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_name: str = Field(..., min_length=3, max_length=200)
    hospital_type: str = "General"
    source: str
    priority: str = "Medium"
    contact_person: str = Field(..., min_length=1, max_length=200)
    designation: str | None = Field(None, max_length=120)
    contact_phone: str = Field(..., max_length=30)
    contact_email: EmailStr | None = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str | None = Field(None, max_length=100)
    plan: str | None = None
    billing_cycle: str | None = None
    message: str | None = None
    shared: bool = False
    allow_duplicate: bool = False

    @field_validator("hospital_name", "contact_person", "city", "source", "hospital_type", "priority")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("designation", "state", "plan", "billing_cycle", "message", "contact_email", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        return _blank(value)

    @field_validator("hospital_type")
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in HOSPITAL_TYPES:
            raise ValueError("Choose a hospital type.")
        return value

    @field_validator("source")
    @classmethod
    def known_source(cls, value: str) -> str:
        if value not in LEAD_SOURCES:
            raise ValueError("Choose a source.")
        return value

    @field_validator("priority")
    @classmethod
    def known_priority(cls, value: str) -> str:
        if value not in PRIORITIES:
            raise ValueError("Choose a priority.")
        return value

    @field_validator("plan")
    @classmethod
    def known_plan(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Choose a subscription plan.")
        return text

    @field_validator("billing_cycle")
    @classmethod
    def known_cycle(cls, value: str | None) -> str | None:
        if value is not None and value not in BILLING_CYCLES:
            raise ValueError("Choose a billing cycle.")
        return value

    @field_validator("contact_phone")
    @classmethod
    def phone_number(cls, value: str) -> str:
        return validate_phone(value)


class LeadContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    outcome: str
    note: str = Field(..., min_length=1, max_length=2000)
    follow_up_date: date | None = None
    next_action: str | None = Field(None, max_length=200)
    reason: str | None = None

    @field_validator("note", "method")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("next_action", "reason", mode="before")
    @classmethod
    def empty_optional(cls, value):
        return _blank(value)

    @field_validator("method")
    @classmethod
    def known_method(cls, value: str) -> str:
        if value not in CONTACT_METHODS:
            raise ValueError("Choose how you contacted them.")
        return value

    @field_validator("outcome")
    @classmethod
    def known_outcome(cls, value: str) -> str:
        if value not in CONTACT_OUTCOMES:
            raise ValueError("Choose the outcome of this contact.")
        return value

    @model_validator(mode="after")
    def outcome_fields(self):
        if self.outcome in ("interested", "callback") and self.follow_up_date is None:
            raise ValueError("Choose the next follow-up date.")
        if self.outcome == "not-interested" and self.reason not in CLOSE_REASONS:
            raise ValueError("Choose a reason.")
        return self


class LeadFollowUp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    follow_up_date: date
    next_action: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=2000)

    @field_validator("next_action", "note", mode="before")
    @classmethod
    def empty_optional(cls, value):
        return _blank(value)


class LeadNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(..., min_length=1, max_length=2000)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Write a note first.")
        return text


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str | None = None
    source: str | None = None
    hospital_type: str | None = None
    contact_person: str | None = Field(None, max_length=200)
    designation: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, max_length=30)
    contact_email: EmailStr | None = None
    hospital_email: EmailStr | None = None
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    plan: str | None = None
    billing_cycle: str | None = None

    @field_validator(
        "priority",
        "source",
        "hospital_type",
        "contact_person",
        "designation",
        "contact_phone",
        "city",
        "state",
        "plan",
        "billing_cycle",
        "contact_email",
        "hospital_email",
        mode="before",
    )
    @classmethod
    def empty_optional(cls, value):
        return _blank(value)

    @field_validator("priority")
    @classmethod
    def known_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in PRIORITIES:
            raise ValueError("Choose a priority.")
        return value

    @field_validator("source")
    @classmethod
    def known_source(cls, value: str | None) -> str | None:
        if value is not None and value not in LEAD_SOURCES:
            raise ValueError("Choose a source.")
        return value

    @field_validator("hospital_type")
    @classmethod
    def known_type(cls, value: str | None) -> str | None:
        if value is not None and value not in HOSPITAL_TYPES:
            raise ValueError("Choose a hospital type.")
        return value

    @field_validator("plan")
    @classmethod
    def known_plan(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Choose a subscription plan.")
        return text

    @field_validator("billing_cycle")
    @classmethod
    def known_cycle(cls, value: str | None) -> str | None:
        if value is not None and value not in BILLING_CYCLES:
            raise ValueError("Choose a billing cycle.")
        return value

    @field_validator("contact_phone")
    @classmethod
    def phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_phone(value)


class LeadAgree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str
    billing_cycle: str
    note: str | None = Field(None, max_length=2000)

    @field_validator("note", mode="before")
    @classmethod
    def empty_note(cls, value):
        return _blank(value)

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


class LeadClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    note: str | None = Field(None, max_length=2000)

    @field_validator("note", mode="before")
    @classmethod
    def empty_note(cls, value):
        return _blank(value)

    @field_validator("reason")
    @classmethod
    def known_reason(cls, value: str) -> str:
        text = value.strip()
        if text not in CLOSE_REASONS:
            raise ValueError("Choose a reason.")
        return text


class LeadActivityOut(BaseModel):
    id: int
    at: str
    actor_id: int
    actor_name: str
    method: str
    note: str
    follow_up_date: str | None = None
    next_action: str | None = None


class LeadSummary(BaseModel):
    id: int
    hospital_name: str
    hospital_type: str
    city: str
    state: str | None = None
    hospital_email: str | None = None
    contact_person: str | None = None
    designation: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    source: str
    priority: str
    plan: str | None = None
    billing_cycle: str | None = None
    message: str | None = None
    status: str
    assigned_to: int | None = None
    created_by: int
    claimed_at: str | None = None
    hospital_id: int | None = None
    registered_at: str | None = None
    registered_by: int | None = None
    registered_by_name: str | None = None
    follow_up_date: str | None = None
    next_action: str | None = None
    handover_note: str | None = None
    agreed_at: str | None = None
    agreed_by: int | None = None
    agreed_by_name: str | None = None
    close_reason: str | None = None
    close_note: str | None = None
    closed_at: str | None = None
    closed_by: int | None = None
    closed_by_name: str | None = None
    contacts_visible: bool
    created_at: str
    activities: list[LeadActivityOut] = []


class LeadDetail(LeadSummary):
    pass
