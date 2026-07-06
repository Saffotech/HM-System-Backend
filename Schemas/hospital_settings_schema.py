from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HospitalSettingsOut(BaseModel):
    id: int
    name: str
    tagline: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    registration_number: Optional[str] = None
    default_registration_fee: float
    default_consultation_fee: float
    default_gst_percent: float
    currency: str
    timezone: str
    updated_at: datetime
    updated_by: Optional[int] = None


class HospitalSettingsUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    tagline: Optional[str] = Field(None, max_length=300)
    address_line1: Optional[str] = Field(None, max_length=300)
    address_line2: Optional[str] = Field(None, max_length=300)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = Field(None, max_length=300)
    gstin: Optional[str] = Field(None, max_length=20)
    pan: Optional[str] = Field(None, max_length=20)
    registration_number: Optional[str] = Field(None, max_length=100)
    default_registration_fee: Optional[float] = Field(None, ge=0)
    default_consultation_fee: Optional[float] = Field(None, ge=0)
    default_gst_percent: Optional[float] = Field(None, ge=0, le=100)
    currency: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=64)
