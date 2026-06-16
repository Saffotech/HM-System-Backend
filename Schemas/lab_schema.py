from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


# =====================================================
# Dashboard
# =====================================================

class DashboardResponse(BaseModel):
    total_today: int
    pending: int
    sample_collected: int
    processing: int
    completed_today: int
    urgent_pending: int


# =====================================================
# Status Update Requests
# =====================================================

class SampleCollectedRequest(BaseModel):
    sample_collected_at: Optional[datetime] = None


class ProcessingRequest(BaseModel):
    test_performed_at: Optional[datetime] = None


# =====================================================
# Lab Parameters
# =====================================================

class LabParameterCreate(BaseModel):
    parameter_name: str = Field(..., min_length=1, max_length=255)
    value: Optional[str] = Field(None, max_length=255)
    unit: Optional[str] = Field(None, max_length=100)
    normal_range: Optional[str] = Field(None, max_length=100)
    flag: Optional[str] = Field(
        None,
        pattern="^(normal|low|high)$"
    )


class LabParameterResponse(BaseModel):
    id: int
    parameter_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    normal_range: Optional[str] = None
    flag: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# Upload Report
# =====================================================

class LabReportCreate(BaseModel):
    sample_collected_at: Optional[datetime] = None
    test_performed_at: Optional[datetime] = None

    report_file: Optional[str] = Field(
        None,
        max_length=500
    )

    remarks: Optional[str] = None

    parameters: List[LabParameterCreate] = Field(default_factory=list)


# =====================================================
# Orders List
# =====================================================

class LabOrderListItem(BaseModel):
    id: int
    appointment_id: int

    patient_id: int
    patient_name: str
    patient_uhid: str

    doctor_id: int
    doctor_name: str

    test_name: str
    category: str
    priority: str

    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LabOrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[LabOrderListItem]


# =====================================================
# Report Summary
# =====================================================

class ReportSummary(BaseModel):
    id: int
    report_file: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# Order Detail
# =====================================================

class LabOrderDetailResponse(BaseModel):
    id: int
    appointment_id: int

    patient_id: int
    patient_name: str
    patient_uhid: str

    doctor_id: int
    doctor_name: str

    test_name: str
    category: str
    priority: str

    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime

    report: Optional[ReportSummary] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# Upload Report Response
# =====================================================

class UploadReportResponse(BaseModel):
    message: str
    report_id: int
    order_id: int
    status: str


# =====================================================
# Reports List
# =====================================================

class LabReportListItem(BaseModel):
    report_id: int
    order_id: int

    patient_name: str
    patient_uhid: str

    test_name: str

    uploaded_by: int
    uploaded_by_name: str

    report_file: Optional[str] = None

    uploaded_at: datetime

    status: str

    model_config = ConfigDict(from_attributes=True)


class LabReportListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[LabReportListItem]


# =====================================================
# Single Report Detail
# =====================================================

class LabReportResponse(BaseModel):
    id: int

    lab_test_order_id: int

    uploaded_by: int
    uploaded_by_name: str

    sample_collected_at: Optional[datetime] = None
    test_performed_at: Optional[datetime] = None

    report_file: Optional[str] = None
    remarks: Optional[str] = None

    created_at: datetime

    parameters: List[LabParameterResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)