from datetime import date, time, datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# ==========================================================
# PATIENT CREATE
# ==========================================================

class ShiftHandoverPatientCreate(BaseModel):

    patient_id: int

    patient_summary: Optional[str] = None

    pending_tasks: Optional[str] = None

    critical_alerts: Optional[str] = None

    medication_pending: Optional[str] = None

    doctor_instructions: Optional[str] = None


# ==========================================================
# BULK PATIENT CREATE
# ==========================================================

class ShiftHandoverPatientsBulkCreate(BaseModel):

    patients: List[ShiftHandoverPatientCreate] = Field(
        ...,
        min_length=1
    )


# ==========================================================
# PATIENT UPDATE
# ==========================================================

class ShiftHandoverPatientUpdate(BaseModel):

    patient_summary: Optional[str] = None

    pending_tasks: Optional[str] = None

    critical_alerts: Optional[str] = None

    medication_pending: Optional[str] = None

    doctor_instructions: Optional[str] = None


# ==========================================================
# HANDOVER CREATE
# ==========================================================

class ShiftHandoverCreate(BaseModel):

    ward_name: str = Field(
        ...,
        min_length=2,
        max_length=150
    )

    department_id: Optional[int] = None

    shift_date: Optional[date] = None

    shift_start: Optional[time] = None

    shift_end: Optional[time] = None

    general_notes: Optional[str] = None


# ==========================================================
# HANDOVER UPDATE
# ==========================================================

class ShiftHandoverUpdate(BaseModel):

    ward_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=150
    )

    department_id: Optional[int] = None

    shift_date: Optional[date] = None

    shift_start: Optional[time] = None

    shift_end: Optional[time] = None

    general_notes: Optional[str] = None


# ==========================================================
# PATIENT RESPONSE
# ==========================================================

class ShiftHandoverPatientResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    patient_id: int

    patient_name: str

    bed_number: Optional[str]

    patient_summary: Optional[str]

    pending_tasks: Optional[str]

    critical_alerts: Optional[str]

    medication_pending: Optional[str]

    doctor_instructions: Optional[str]

    created_at: datetime


# ==========================================================
# HANDOVER LIST RESPONSE
# ==========================================================

class ShiftHandoverListResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    handover_uid: str

    outgoing_nurse_id: int

    ward_name: str

    shift_date: date

    status: str

    submitted_at: Optional[datetime]

    created_at: datetime


# ==========================================================
# HANDOVER DETAIL RESPONSE
# ==========================================================

class ShiftHandoverDetailResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    handover_uid: str

    outgoing_nurse_id: int

    department_id: Optional[int]

    ward_name: str

    shift_date: date

    shift_start: Optional[time]

    shift_end: Optional[time]

    general_notes: Optional[str]

    status: str

    submitted_at: Optional[datetime]

    created_at: datetime

    updated_at: datetime

    patients: List[ShiftHandoverPatientResponse]


# ==========================================================
# HANDOVER LIST PAGINATION RESPONSE
# ==========================================================

class ShiftHandoverPaginatedResponse(BaseModel):

    total_records: int

    page: int

    limit: int

    data: List[ShiftHandoverListResponse]


# ==========================================================
# COMMON MESSAGE RESPONSE
# ==========================================================

class MessageResponse(BaseModel):

    message: str