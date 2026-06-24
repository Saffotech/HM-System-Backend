from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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
    duration: int
    instructions: Optional[str] = None
    quantity_prescribed: int = 0
    quantity_dispensed: int = 0
    quantity_remaining: int = 0

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
    items: List[PharmacyPrescriptionItemOut]


class DispenseItemRequest(BaseModel):
    prescription_item_id: int
    quantity_dispensed: int = Field(..., gt=0)


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


class DispenseResponse(BaseModel):
    message: str
    dispensing_id: int
    prescription_id: int
    status: str
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
    status: str
    dispensed_at: datetime


class DispenseHistoryResponse(BaseModel):
    total: int
    history: List[DispenseHistoryItem]
