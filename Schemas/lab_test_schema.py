from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ==========================================
# Create Lab Test
# ==========================================

class LabTestCreate(BaseModel):
    appointment_id: int

    test_name: str = Field(
        ...,
        min_length=1,
        max_length=255
    )

    category: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    priority: str = Field(
        default="Normal",
        max_length=50
    )

    clinical_notes: Optional[str] = Field(
        default=None,
        max_length=500
    )


# ==========================================
# Update Lab Test
# ==========================================

class LabTestUpdate(BaseModel):
    test_name: Optional[str] = Field(
        default=None,
        max_length=255
    )

    category: Optional[str] = Field(
        default=None,
        max_length=100
    )

    priority: Optional[str] = Field(
        default=None,
        max_length=50
    )

    clinical_notes: Optional[str] = Field(
        default=None,
        max_length=500
    )


# ==========================================
# Lab Test Response
# ==========================================

class LabTestResponse(BaseModel):
    id: int
    appointment_id: int

    patient_id: int
    patient_name: str
    patient_uhid: str

    doctor_id: int

    test_name: str
    category: str
    priority: str
    clinical_notes: Optional[str]

    status: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# Lab Test List Response
# ==========================================

class LabTestListResponse(BaseModel):
    id: int

    patient_id: int
    patient_name: str
    patient_uhid: str

    test_name: str
    category: str

    status: str

    created_at: datetime

    class Config:
        from_attributes = True