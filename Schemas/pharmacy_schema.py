from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from Services.prescription_duration import normalize_duration


class PharmacyPrescriptionListItem(BaseModel):
    id: int
    patient_id: int
    patient_uid: str
    patient_name: str
    doctor_name: str
    diagnosis: str
    medicine_count: int
    status: str
    created_at: datetime


class PharmacyPrescriptionListResponse(BaseModel):
    total: int
    prescriptions: List[PharmacyPrescriptionListItem]


class PharmacyPrescriptionItemOut(BaseModel):
    id: int
    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None
    form: Optional[str] = None
    route: Optional[str] = None
    timing: Optional[str] = None
    quantity: Optional[int] = None
    quantity_prescribed: int = 0
    quantity_dispensed: int = 0
    quantity_remaining: int = 0
    # Aggregated across all dispenses for this line
    unit_price: float = 0.0
    amount_dispensed: float = 0.0

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration(cls, v):
        return normalize_duration(v) if v is not None else ""

    class Config:
        from_attributes = True


class PharmacyPrescriptionDetail(BaseModel):
    id: int
    patient_id: int
    patient_uid: str
    patient_name: str
    patient_phone: Optional[str] = None
    allergies: Optional[str] = None
    doctor_name: str
    diagnosis: str
    notes: Optional[str] = None
    status: str
    created_at: datetime
    total_amount_dispensed: float = 0.0
    items: List[PharmacyPrescriptionItemOut]


class DispenseItemRequest(BaseModel):
    prescription_item_id: int
    quantity_dispensed: int = Field(..., gt=0)
    # Line total $ entered by pharmacist (source of truth for pricing)
    amount: float = Field(..., ge=0)


class DispenseRequest(BaseModel):
    items: List[DispenseItemRequest] = Field(..., min_length=1)
    remarks: Optional[str] = None
    batch_number: Optional[str] = None


class DispenseItemResponse(BaseModel):
    prescription_item_id: int
    medicine_name: str
    quantity_dispensed: int
    quantity_prescribed: int
    quantity_remaining: int
    unit_price: float
    amount: float


class DispenseResponse(BaseModel):
    message: str
    dispensing_id: int
    prescription_id: int
    status: str
    total_amount: float
    items: List[DispenseItemResponse]


class DispenseHistoryItem(BaseModel):
    id: int
    dispensing_id: int
    patient_uid: Optional[str] = None
    prescription_id: int
    prescription_item_id: int
    medicine_name: str
    patient_name: str
    pharmacist_name: str
    quantity_dispensed: int
    unit_price: float = 0.0
    amount: float = 0.0
    status: str
    dispensed_at: datetime


class DispenseHistoryResponse(BaseModel):
    total: int
    history: List[DispenseHistoryItem]
