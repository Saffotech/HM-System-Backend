from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from datetime import datetime
from typing import List, Optional

from Schemas.common_schema import PaginatedResponse
from Schemas.lab_schema import ReportSource


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
    patient_uid: str = Field(
        validation_alias=AliasChoices("patient_uid", "patient_uhid")
    )

    doctor_id: int

    test_name: str
    category: str
    priority: str
    clinical_notes: Optional[str]

    status: str

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==========================================
# Lab Test List Response
# ==========================================

class LabTestListResponse(BaseModel):
    id: int

    patient_id: int
    patient_name: str
    patient_uid: str = Field(
        validation_alias=AliasChoices("patient_uid", "patient_uhid")
    )

    test_name: str
    category: str
    priority: str

    status: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LabTestListPaginatedResponse(PaginatedResponse[LabTestListResponse]):
    pass


class LabTestReportSummary(BaseModel):
    id: int
    report_file: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    source: Optional[str] = None


class LabTestDetailResponse(BaseModel):
    id: int
    appointment_id: int

    patient_id: int
    patient_name: str
    patient_uid: str = Field(
        validation_alias=AliasChoices("patient_uid", "patient_uhid")
    )

    doctor_id: int

    test_name: str
    category: str
    priority: str
    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime
    updated_at: datetime

    report_uploaded: bool = False
    has_report: bool = False
    report: Optional[LabTestReportSummary] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==========================================
# Doctor Lab Report History
# ==========================================

class DoctorLabReportListItem(BaseModel):
    report_id: int
    order_id: int
    patient_id: int
    patient_name: str
    patient_uid: str
    test_name: str
    category: str
    status: str
    source: str
    has_file: bool
    uploaded_at: datetime
    uploaded_by_name: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DoctorLabReportListResponse(PaginatedResponse[DoctorLabReportListItem]):
    pass


class DoctorLabReportParameter(BaseModel):
    id: int
    parameter_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    normal_range: Optional[str] = None
    flag: Optional[str] = None


class DoctorLabReportDetailResponse(BaseModel):
    report_id: int
    order_id: int
    patient_id: int
    patient_name: str
    patient_uid: str
    test_name: str
    category: str
    priority: str
    order_status: str
    source: str
    sample_collected_at: Optional[datetime] = None
    test_performed_at: Optional[datetime] = None
    remarks: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_by_name: str
    uploaded_at: datetime
    parameters: List[DoctorLabReportParameter] = Field(default_factory=list)
