from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DeleteControlsOut(BaseModel):
    allow_patient_delete: bool = True
    allow_appointment_delete: bool = True
    allow_unpaid_bill_delete: bool = True
    require_admin_approval_for_delete: bool = True


class DeleteControlsUpdate(BaseModel):
    allow_patient_delete: Optional[bool] = None
    allow_appointment_delete: Optional[bool] = None
    allow_unpaid_bill_delete: Optional[bool] = None
    require_admin_approval_for_delete: Optional[bool] = None


class DepartmentConsultationFee(BaseModel):
    department_id: int
    department_name: str = ""
    fee: float = Field(..., ge=0)


class DoctorConsultationFee(BaseModel):
    doctor_id: int
    doctor_name: str = ""
    department_id: Optional[int] = None
    department_name: str = ""
    fee: float = Field(..., ge=0)


class BillItemPrice(BaseModel):
    id: Optional[str] = None
    name: str
    price: float = Field(..., ge=0)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned:
            raise ValueError("Bill item name is required")
        return cleaned


class WardBedTariff(BaseModel):
    ward_name: str
    charge_per_day: float = Field(..., ge=0)

    @field_validator("ward_name")
    @classmethod
    def ward_name_not_blank(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned:
            raise ValueError("Ward name is required")
        return cleaned


class SpecialBedTariff(BaseModel):
    bed_number: str
    ward_name: str = ""
    charge_per_day: float = Field(..., ge=0)

    @field_validator("bed_number", "ward_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return (v or "").strip()


class BedTariffOut(BaseModel):
    general_ward_charge: float = Field(500.0, ge=0)
    private_ward_charge: float = Field(2000.0, ge=0)
    icu_charge: float = Field(5000.0, ge=0)
    ward_rates: list[WardBedTariff] = Field(default_factory=list)
    special_bed_rates: list[SpecialBedTariff] = Field(default_factory=list)


class BedTariffUpdate(BaseModel):
    general_ward_charge: Optional[float] = Field(None, ge=0)
    private_ward_charge: Optional[float] = Field(None, ge=0)
    icu_charge: Optional[float] = Field(None, ge=0)
    ward_rates: Optional[list[WardBedTariff]] = None
    special_bed_rates: Optional[list[SpecialBedTariff]] = None


class PricingOut(BaseModel):
    registration_fee: float = Field(200.0, ge=0)
    consultation_fee: float = Field(500.0, ge=0)
    gst_percent: float = Field(5.0, ge=0)
    allow_manual_price_entry: bool = True
    bed_tariff: BedTariffOut = Field(default_factory=BedTariffOut)
    department_consultation_fees: list[DepartmentConsultationFee] = Field(default_factory=list)
    doctor_consultation_fees: list[DoctorConsultationFee] = Field(default_factory=list)
    bill_items: list[BillItemPrice] = Field(default_factory=list)


class PricingUpdate(BaseModel):
    registration_fee: Optional[float] = Field(None, ge=0)
    consultation_fee: Optional[float] = Field(None, ge=0)
    gst_percent: Optional[float] = Field(None, ge=0)
    allow_manual_price_entry: Optional[bool] = None
    bed_tariff: Optional[BedTariffUpdate] = None
    department_consultation_fees: Optional[list[DepartmentConsultationFee]] = None
    doctor_consultation_fees: Optional[list[DoctorConsultationFee]] = None
    bill_items: Optional[list[BillItemPrice]] = None


class DiscountRefundOut(BaseModel):
    allow_discount: bool = True
    max_discount_percent: float = Field(10.0, ge=0, le=100)
    require_admin_approval_for_discount: bool = True
    allow_refund: bool = True
    require_admin_approval_for_refund: bool = True
    allow_cancel_paid_bill: bool = False


class DiscountRefundUpdate(BaseModel):
    allow_discount: Optional[bool] = None
    max_discount_percent: Optional[float] = Field(None, ge=0, le=100)
    require_admin_approval_for_discount: Optional[bool] = None
    allow_refund: Optional[bool] = None
    require_admin_approval_for_refund: Optional[bool] = None
    allow_cancel_paid_bill: Optional[bool] = None


class PaymentMode(BaseModel):
    code: str
    label: str = ""
    enabled: bool = True

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        if not cleaned:
            raise ValueError("Payment mode code is required")
        return cleaned


class BankDetails(BaseModel):
    account_name: str = ""
    bank_name: str = ""
    account_number: str = ""
    ifsc: str = ""
    upi_id: str = ""


class InsuranceProvider(BaseModel):
    id: Optional[str] = None
    name: str = ""
    code: str = ""
    is_active: bool = True

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return (v or "").strip()


class PaymentSettingsOut(BaseModel):
    modes: list[PaymentMode] = Field(default_factory=list)
    bank_details: BankDetails = Field(default_factory=BankDetails)
    insurance_providers: list[InsuranceProvider] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_duplicate_modes(self):
        codes = [m.code for m in self.modes]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate payment mode codes")
        return self

    @model_validator(mode="after")
    def no_duplicate_provider_codes(self):
        codes = [p.code for p in self.insurance_providers if p.code]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate insurance provider codes")
        return self


class PaymentSettingsUpdate(BaseModel):
    modes: Optional[list[PaymentMode]] = None
    bank_details: Optional[BankDetails] = None
    insurance_providers: Optional[list[InsuranceProvider]] = None


class OpdSettingsOut(BaseModel):
    delete_controls: DeleteControlsOut
    pricing: PricingOut
    discount_refund: DiscountRefundOut
    appointment_slots: Optional[dict[str, Any]] = None
    payment_modes: PaymentSettingsOut
    admin_edit: dict[str, bool] = Field(default_factory=dict)
    updated_at: Optional[str] = None
    updated_by: Optional[int] = None


class OpdSettingsUpdate(BaseModel):
    delete_controls: Optional[DeleteControlsUpdate] = None
    pricing: Optional[PricingUpdate] = None
    discount_refund: Optional[DiscountRefundUpdate] = None
    appointment_slots: Optional[dict[str, Any]] = None
    payment_modes: Optional[PaymentSettingsUpdate] = None
    admin_edit: Optional[dict[str, bool]] = None

    model_config = {"extra": "ignore"}
