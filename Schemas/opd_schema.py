"""OPD visit, billing, and API response schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from Schemas.patient_schema import PatientFields


class VisitBillingFields(BaseModel):
    department_id: int
    doctor_id: int
    registration_fee: float = Field(200.0, ge=0)
    consultation_fee: float = Field(800.0, ge=0)
    gst_percent: float = Field(5.0, ge=0, le=100)


class BillPreviewRequest(BaseModel):
    """Preview totals — fees only, no patient/visit required."""

    registration_fee: float = Field(200.0, ge=0)
    consultation_fee: float = Field(800.0, ge=0)
    gst_percent: float = Field(5.0, ge=0, le=100)


class PatientRegisterRequest(PatientFields, VisitBillingFields):
    """New patient + first OPD visit + payment (single front-desk flow)."""
    aadhaar_number: str = Field(
        ...,
        min_length=12,
        max_length=12,
        pattern=r"^\d{12}$",
        description="12-digit Aadhaar number",
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Booked doctor slot; when omitted, defaults to now (IST)",
    )
    appointment_id: Optional[int] = Field(
        None,
        description="Reuse an existing appointment when provided",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "Amaresh",
                "last_name": "Maurya",
                "phone": "9567154627",
                "aadhaar_number": "123456789012",
                "gender": 1,
                "department_id": 1,
                "doctor_id": 2,
                "registration_fee": 200.0,
                "consultation_fee": 800.0,
                "gst_percent": 5.0,
                "scheduled_at": "2026-07-14T13:00:00+05:30",
            }
        }


# Backward-compatible name used by existing clients
PatientCreate = PatientRegisterRequest


class OpdVisitCreate(VisitBillingFields):
    """Existing patient — new OPD visit + bill."""

    patient_id: int
    appointment_id: Optional[int] = None
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Doctor slot for this revisit; resolves/creates one appointment",
    )
    waive_registration_fee: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": 1,
                "department_id": 1,
                "doctor_id": 2,
                "registration_fee": 0,
                "consultation_fee": 800.0,
                "gst_percent": 5.0,
                "waive_registration_fee": True,
                "scheduled_at": "2026-07-14T13:30:00+05:30",
            }
        }


class CollectPayment(BaseModel):
    payment_mode: str = "cash"
    paid_amount: float = Field(..., gt=0)
    transaction_reference: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "payment_mode": "upi",
                "paid_amount": 500.0,
                "transaction_reference": "TXN123456",
            }
        }


class ExtraBillItem(BaseModel):
    description: str
    qty: int = Field(1, ge=1)
    unit_price: float = Field(..., ge=0)


class GenerateBillRequest(BaseModel):
    """Generate bill for existing patient with optional extra line items."""

    patient_id: int
    department_id: int
    doctor_id: int
    registration_fee: float = Field(0, ge=0)
    consultation_fee: float = Field(800.0, ge=0)
    gst_percent: float = Field(5.0, ge=0, le=100)
    extra_items: List[ExtraBillItem] = []
    pay_later: bool = False
    payment_mode: str = "cash"
    amount_received: Optional[float] = None
    transaction_reference: Optional[str] = None


class BillUpdateRequest(BaseModel):
    """Update an existing bill — only sent fields are changed."""

    department_id: Optional[int] = None
    doctor_id: Optional[int] = None
    registration_fee: Optional[float] = Field(None, ge=0)
    consultation_fee: Optional[float] = Field(None, ge=0)
    gst_percent: Optional[float] = Field(None, ge=0, le=100)
    extra_items: Optional[List[ExtraBillItem]] = None


class BillLineItem(BaseModel):
    description: str
    qty: int
    unit_price: float
    amount: float


class BillSummary(BaseModel):
    subtotal: float
    gst_percent: float
    gst_amount: float
    grand_total: float


class BillPreviewResponse(BaseModel):
    bill_items: List[BillLineItem]
    summary: BillSummary


class RegisterSuccessResponse(BaseModel):
    message: str
    patient_id: int
    patient_uid: str
    bill_number: str
    token_number: str
    visit_id: int
    appointment_id: Optional[int] = None
    appointment_uid: Optional[str] = None
    scheduled_at: Optional[str] = None


class VisitSuccessResponse(BaseModel):
    message: str
    patient_id: int
    patient_uid: str
    bill_number: str
    token_number: str
    visit_id: int
    grand_total: float
    payment_status: str
    appointment_id: Optional[int] = None
    appointment_uid: Optional[str] = None
    scheduled_at: Optional[str] = None


class QueueVisitItem(BaseModel):
    visit_id: int
    token_number: str
    bill_number: str
    visit_date: Optional[str]
    patient_id: Optional[int] = None
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_name: Optional[str]
    department: Optional[str]
    status: str
    payment_status: str
    grand_total: float
    payment_mode: Optional[str]


class QueueResponse(BaseModel):
    total: int
    visits: List[QueueVisitItem]


class BillingVisitsTodayResponse(BaseModel):
    """Today's OPD billing visits — not the clinical doctor queue."""

    source: str = "opd_visits"
    description: str = (
        "Registered OPD visits and bills for today. "
        "This is NOT the clinical waiting-room queue. "
        "For check-in, doctor queue, and pending calls use /receptionist/*."
    )
    total: int
    visits: List[QueueVisitItem]


class BillListItem(BaseModel):
    visit_id: int
    bill_number: str
    token_number: str
    patient_id: int
    patient_uid: str
    patient_name: str
    grand_total: float
    paid_amount: Optional[float]
    balance_due: float
    payment_status: str
    visit_date: Optional[str]


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    department_id: int
    scheduled_at: datetime
    reason: Optional[str] = None
    notes: Optional[str] = None
    appointment_type: str = "opd"


class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None


class AppointmentOut(BaseModel):
    id: int
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_uid: str
    doctor_id: int
    doctor_name: str
    department_id: int
    department_name: str
    scheduled_at: str
    reason: Optional[str]
    notes: Optional[str]
    appointment_type: str
    status: str
    payment_status: Optional[str] = None
    bill_id: Optional[int] = None
    bill_number: Optional[str] = None
    total_amount: float = 0.0
    paid_amount: float = 0.0
    balance_amount: float = 0.0


class BedOut(BaseModel):
    id: int
    bed_number: str
    ward_name: str
    department_id: Optional[int]
    department_name: Optional[str]
    patient_id: Optional[int]
    patient_name: Optional[str]
    patient_uid: Optional[str]
    status: str
    admitted_at: Optional[str]


class AssignBedRequest(BaseModel):
    bed_id: int
    patient_id: int
    department_id: Optional[int] = None
