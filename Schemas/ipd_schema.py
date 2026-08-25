"""Pydantic schemas for IPD admissions, beds, billing, and discharge."""
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from Schemas.patient_schema import PatientFields, PatientOut


class IpdPatientRegisterRequest(PatientFields):
    """
    Patient Master registration for IPD — demographics only.
    Does not create OPD visit, appointment, token, or bill.
    """

    aadhaar_number: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")


class IpdPatientRegisterResponse(BaseModel):
    message: str = "Patient registered successfully"
    patient_id: int
    patient_uid: str
    patient: PatientOut


class IpdAdmitInsuranceIn(BaseModel):
    """Insurance profile captured at admit (cashless / copay)."""

    claim_type: str = Field(..., description="cashless | pay_and_claim")
    insurer: str = Field(..., min_length=1)
    policy_no: str = Field(..., min_length=1)
    policy_holder: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    member_id: Optional[str] = None
    claimed_amount: float = Field(0, ge=0)
    estimate_amount: Optional[float] = Field(None, ge=0)

    @model_validator(mode="after")
    def normalize_claim_type(self):
        key = (self.claim_type or "").strip().lower().replace("-", "_")
        if key in {"cashless", "insurance_cashless"}:
            self.claim_type = "cashless"
        elif key in {"pay_and_claim", "copay", "co_pay", "insurance_copay"}:
            self.claim_type = "pay_and_claim"
        else:
            raise ValueError("claim_type must be cashless or pay_and_claim")
        return self


class IpdAdmitRequest(BaseModel):
    patient_id: int
    bed_id: int
    doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    admission_date: Optional[str] = None  # ISO datetime; default now
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    # self | insurance (default self for backwards compatibility)
    payment_mode: Optional[str] = "self"
    self_pay_method: Optional[str] = None  # cash | card | upi
    insurance: Optional[IpdAdmitInsuranceIn] = None

    @model_validator(mode="after")
    def validate_payment(self):
        mode = (self.payment_mode or "self").strip().lower()
        if mode in {"insurance", "cashless", "copay"}:
            mode = "insurance"
        elif mode in {"self", "self_pay", "self-pay"}:
            mode = "self"
        else:
            raise ValueError("payment_mode must be self or insurance")
        self.payment_mode = mode

        if mode == "insurance":
            if not self.insurance:
                raise ValueError("insurance details are required when payment_mode is insurance")
            self.self_pay_method = None
        else:
            self.insurance = None
            method = (self.self_pay_method or "").strip().lower()
            if method and method not in {"cash", "card", "upi"}:
                raise ValueError("self_pay_method must be cash, card, or upi")
            self.self_pay_method = method or None
        return self


class IpdAdmissionUpdate(BaseModel):
    doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class IpdTransferBedRequest(BaseModel):
    """Transfer by admission id, or by occupied source bed (creates admission if missing)."""

    admission_id: Optional[int] = None
    from_bed_id: Optional[int] = None
    new_bed_id: int

    @model_validator(mode="after")
    def require_source(self):
        if not self.admission_id and not self.from_bed_id:
            raise ValueError("Provide admission_id or from_bed_id")
        return self


class IpdDoctorVisitCreate(BaseModel):
    doctor_id: int
    charge: Optional[float] = Field(None, ge=0)
    visited_at: Optional[str] = None
    notes: Optional[str] = None


class IpdBillItemIn(BaseModel):
    description: str
    qty: int = Field(default=1, ge=1)
    unit_price: float = Field(ge=0)
    item_type: str = "misc"


class IpdGenerateBillRequest(BaseModel):
    admission_id: int
    extra_items: List[IpdBillItemIn] = Field(default_factory=list)
    gst_percent: Optional[float] = None
    pay_later: bool = True
    payment_mode: Optional[str] = None
    amount_received: float = 0
    transaction_reference: Optional[str] = None


class IpdCollectPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    payment_mode: str
    transaction_reference: Optional[str] = None


class IpdDischargeRequest(BaseModel):
    force: bool = False  # allow discharge with unpaid balance only if true (admin override)
    notes: Optional[str] = None


class IpdAdmissionOut(BaseModel):
    id: int
    admission_no: str
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    bed_id: Optional[int] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    status: str
    payment_type: str = "self"
    self_pay_method: Optional[str] = None
    claim_id: Optional[int] = None
    coverage: Optional[str] = None
    insurer: Optional[str] = None
    policy_no: Optional[str] = None
    admitted_at: Optional[str] = None
    discharged_at: Optional[str] = None
    length_of_stay_days: Optional[int] = None


class IpdInsuranceClaimUpdate(BaseModel):
    insurer: Optional[str] = Field(None, min_length=1)
    policy_no: Optional[str] = Field(None, min_length=1, alias="policyNo")
    policy_holder: Optional[str] = Field(None, min_length=1, alias="policyHolder")
    relationship: Optional[str] = None
    member_id: Optional[str] = Field(None, alias="memberId")
    claimed_amount: Optional[float] = Field(None, ge=0, alias="claimedAmount")
    # FE also sends claimed
    claimed: Optional[float] = Field(None, ge=0)
    estimate_amount: Optional[float] = Field(None, ge=0, alias="estimateAmount")
    policy_status: Optional[str] = Field(None, alias="policyStatus")
    claim_status: Optional[str] = Field(None, alias="claimStatus")
    approved_amount: Optional[float] = Field(None, ge=0, alias="approvedAmount")
    available_si: Optional[float] = Field(None, ge=0, alias="availableSi")

    model_config = {"populate_by_name": True}


class IpdInsurancePaymentIn(BaseModel):
    amount: float = Field(..., gt=0)
    paid_at: Optional[str] = Field(None, alias="paidAt")
    reference: Optional[str] = None
    notes: Optional[str] = None
    mode: Optional[str] = None

    model_config = {"populate_by_name": True}

class IpdDoctorVisitOut(BaseModel):
    id: int
    admission_id: int
    doctor_id: int
    doctor_name: Optional[str] = None
    visited_at: Optional[str] = None
    charge: float
    notes: Optional[str] = None


class IpdBillItemOut(BaseModel):
    id: Optional[int] = None
    description: str
    qty: int
    unit_price: float
    amount: float
    item_type: str = "misc"


class IpdBillOut(BaseModel):
    id: int
    bill_number: str
    admission_id: int
    subtotal: float
    gst_percent: float
    gst_amount: float
    grand_total: float
    payment_status: str
    payment_mode: Optional[str] = None
    paid_amount: float
    balance_due: float
    status: str
    generated_at: Optional[str] = None
    items: List[IpdBillItemOut] = Field(default_factory=list)


class IpdBillPreviewOut(BaseModel):
    admission_id: int
    admission_no: str
    patient_name: Optional[str] = None
    ward_name: Optional[str] = None
    bed_number: Optional[str] = None
    length_of_stay_days: int
    bed_rate: float
    items: List[IpdBillItemOut]
    subtotal: float
    gst_percent: float
    gst_amount: float
    grand_total: float
