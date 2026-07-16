from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, AliasChoices

from Schemas.common_schema import PaginatedResponse


# =====================================================
# Enums
# =====================================================

class ReportSource(str, Enum):
    PARAMETERS = "PARAMETERS"
    PDF = "PDF"
    BOTH = "BOTH"


class LabTestCategoryItem(BaseModel):
    value: str
    label: str
    requires_sample: bool


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


class StatusUpdateResponse(BaseModel):
    message: str
    order_id: int
    status: str


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
    patient_uid: str

    doctor_id: int
    doctor_name: str

    test_name: str
    category: str
    requires_sample: bool
    priority: str

    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LabOrderListResponse(PaginatedResponse[LabOrderListItem]):
    pass


# =====================================================
# Report Summary
# =====================================================

class ReportSummary(BaseModel):
    id: int
    report_file: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# Order Detail
# =====================================================

class LabOrderDetailResponse(BaseModel):
    id: int
    appointment_id: int

    patient_id: int
    patient_name: str
    patient_uid: str

    doctor_id: int
    doctor_name: str

    test_name: str
    category: str
    requires_sample: bool
    priority: str

    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime

    report: Optional[ReportSummary] = None
    report_uploaded: bool = False
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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

    patient_id: int
    patient_name: str
    patient_uid: str

    test_name: str

    uploaded_by: int
    uploaded_by_name: str

    report_file: Optional[str] = None

    uploaded_at: datetime

    status: str
    source: str

    model_config = ConfigDict(from_attributes=True)


class LabReportListResponse(PaginatedResponse[LabReportListItem]):
    pass


# =====================================================
# Single Report Detail
# =====================================================

class LabReportOrderSummary(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_uid: str
    doctor_id: int
    test_name: str
    category: str
    priority: str
    status: str


class LabReportDetailResponse(BaseModel):
    id: int

    lab_test_order_id: int

    uploaded_by: int
    uploaded_by_name: str

    sample_collected_at: Optional[datetime] = None
    test_performed_at: Optional[datetime] = None

    report_file: Optional[str] = None
    remarks: Optional[str] = None

    created_at: datetime
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    file_size_display: Optional[str] = None
    source: str

    order: LabReportOrderSummary
    parameters: List[LabParameterResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


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
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    file_size_display: Optional[str] = None
    source: Optional[str] = None

    parameters: List[LabParameterResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CompleteTestResponse(BaseModel):
    message: str
    order_id: int
    status: str


class UploadReportFileResponse(BaseModel):
    message: str
    report_id: int
    order_id: int
    file_name: str
    file_type: Optional[str] = None
    file_size: int
