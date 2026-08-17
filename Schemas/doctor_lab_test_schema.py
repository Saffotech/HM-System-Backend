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

    # Optional for existing clients; when omitted, backend infers LAB vs RAD.
    department_id: Optional[int] = None

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

    department_id: Optional[int] = None

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
    registration_source: str

    doctor_id: int
    department_id: int

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
    registration_source: str

    department_id: int

    test_name: str
    category: str
    priority: str
    clinical_notes: Optional[str] = None

    status: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LabTestListPaginatedResponse(PaginatedResponse[LabTestListResponse]):
    pass


# ==========================================
# Doctor Lab Report Detail
# ==========================================

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
    registration_source: str
    test_name: str
    category: str
    department_id: Optional[int] = None
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
