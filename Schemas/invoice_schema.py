from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

PAYMENT_METHODS = ("Bank transfer", "UPI", "Card", "Cheque")
INVOICE_STATUSES = ("Pending", "Overdue", "Paid", "Failed")


class RecordPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(..., gt=0)
    method: str
    reference: str | None = Field(None, max_length=100)
    paid_at: date
    notes: str | None = Field(None, max_length=2000)

    @field_validator("method")
    @classmethod
    def known_method(cls, value: str) -> str:
        text = value.strip()
        if text not in PAYMENT_METHODS:
            raise ValueError("Choose a payment method.")
        return text

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def blank(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class InvoiceOut(BaseModel):
    id: int
    number: str
    tenant_id: int
    hospital_name: str
    hospital_code: str
    plan: str
    billing_cycle: str
    subscription_status: str
    amount: int
    invoice_date: date
    due_date: date
    status: str
    method: str | None = None
    reference: str | None = None
    paid_at: date | None = None
    notes: str | None = None
    payment_amount: int | None = None
    recorded_by_name: str | None = None
