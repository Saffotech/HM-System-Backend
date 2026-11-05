from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LegalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["Approved", "Conditionally Approved", "Changes Requested", "Rejected"]
    reason: str = Field(..., max_length=2000)
    condition: str | None = Field(None, max_length=2000)
    condition_owner: Literal["Accounts Team", "Sales Owner"] | None = None

    @field_validator("reason", "condition")
    @classmethod
    def reason_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Enter the reason.")
        return value


class ChecklistItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    status: Literal["Pending", "Verified", "Issue Found", "Not applicable"]
    note: str | None = Field(None, max_length=2000)

    @field_validator("note")
    @classmethod
    def note_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class LegalChecklistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ChecklistItemUpdate]


class LegalFinanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discount: int = Field(..., ge=0, le=100)
    standard_price: int = Field(0, ge=0, le=10_000_000)
    years: int = Field(1, ge=1, le=10)
    implementation_fee: int = Field(0, ge=0, le=10_000_000)
    training_fee: int = Field(0, ge=0, le=10_000_000)
    tax_percent: int = Field(0, ge=0, le=100)
    advance_percent: int = Field(0, ge=0, le=100)
    credit_days: int = Field(0, ge=0, le=365)
    frequency: Literal["Annual", "Half-yearly", "Quarterly", "Monthly"] = "Annual"
    modules: str | None = Field(None, max_length=200)
    gstin: str | None = Field(None, max_length=20)
    po_required: Literal["Yes", "No"] = "No"
    invoice_email: str | None = Field(None, max_length=200)


class EscalationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["Approved", "Rejected"]


class LegalDocumentOut(BaseModel):
    id: int
    category: str
    file_name: str
    status: str
    uploaded_by: int | None = None
    reviewed_by: int | None = None
    reviewed_at: str | None = None


class ChecklistItemOut(BaseModel):
    id: int
    label: str
    status: str
    note: str | None = None
    updated_by: int | None = None
    updated_at: str | None = None


class LegalFinanceOut(BaseModel):
    standard_price: int
    discount: int
    years: int
    implementation_fee: int
    training_fee: int
    tax_percent: int
    advance_percent: int
    credit_days: int
    frequency: str
    modules: str | None = None
    gstin: str | None = None
    po_required: str
    invoice_email: str | None = None
    reviewed: bool
    updated_by: int | None = None
    updated_at: str | None = None


class LegalDecisionOut(BaseModel):
    status: str
    reason: str
    condition: str | None = None
    condition_owner: str | None = None


class LegalCaseOut(BaseModel):
    id: int
    lead_id: int
    hospital_name: str
    city: str | None = None
    plan: str | None = None
    status: str
    decision_reason: str | None = None
    discount: int = 0
    escalation: str = "Not needed"
    escalation_by: int | None = None
    escalation_at: str | None = None
    documents: list[LegalDocumentOut] = []
    checklist: list[ChecklistItemOut] = []
    finance: LegalFinanceOut | None = None
    decision: LegalDecisionOut | None = None
    advance_received: bool
    ready_to_register: bool
