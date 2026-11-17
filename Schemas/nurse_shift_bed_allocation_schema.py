
from datetime import date, datetime, time
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

from Schemas.common_schema import PaginatedResponse


# ==========================================================
# Filters
# ==========================================================

AllocationStatus = Literal[
    "active",
    "completed",
    "deactivated",
]


class NurseShiftBedAllocationFilter(BaseModel):
    nurse_id: Optional[int] = Field(None, ge=1)
    bed_id: Optional[int] = Field(None, ge=1)
    department_id: Optional[int] = Field(None, ge=1)
    shift_date: Optional[date] = None
    shift_name: Optional[str] = Field(None, max_length=100)
    ward_name: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[AllocationStatus] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ==========================================================
# Request
# ==========================================================

class NurseShiftBedAllocationCreate(BaseModel):
    nurse_id: int = Field(..., ge=1)
    bed_id: int = Field(..., ge=1)
    shift_date: date
    assigned_until: Optional[date] = None

    shift_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional. Filled from the nurse roster for shift_date when omitted.",
    )

    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    department_id: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None


class NurseShiftBedAllocationBulkCreate(BaseModel):
    nurse_id: int = Field(..., ge=1)
    bed_ids: List[int] = Field(..., min_length=1)
    shift_date: date
    assigned_until: Optional[date] = None

    shift_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional. Filled from the nurse roster for shift_date when omitted.",
    )

    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    department_id: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None


class NurseShiftBedAllocationUpdate(BaseModel):
    nurse_id: Optional[int] = Field(None, ge=1)
    bed_id: Optional[int] = Field(None, ge=1)
    shift_date: Optional[date] = None
    assigned_until: Optional[date] = None

    shift_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
    )

    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    department_id: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


# ==========================================================
# Response
# ==========================================================

class NurseShiftBedAllocationItem(BaseModel):
    # Allocation identification
    id: int

    # Nurse information
    nurse_id: int
    nurse_name: Optional[str] = None
    nurse_email: Optional[str] = None

    # Bed information
    bed_id: int
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None

    # Allocation dates
    shift_date: date
    assigned_until: Optional[date] = None
    ended_at: Optional[datetime] = None

    # Shift information
    shift_name: str = ""
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None

    # Department information
    department_id: Optional[int] = None
    department_name: Optional[str] = None

    # Original assignment information
    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None

    # Allocation lifecycle
    status: str = "active"
    is_active: bool = True

    # Latest status-change history
    status_action: Optional[str] = None
    status_changed_by_name: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    status_remarks: Optional[str] = None

    # Additional information
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NurseShiftBedAllocationListResponse(
    PaginatedResponse[NurseShiftBedAllocationItem]
):
    pass


class NurseShiftBedAllocationDetailResponse(BaseModel):
    success: bool = True
    data: NurseShiftBedAllocationItem


class NurseShiftBedAllocationBulkResponse(BaseModel):
    success: bool = True
    created: int = 0
    skipped: int = 0
    items: List[NurseShiftBedAllocationItem] = Field(
        default_factory=list
    )
    errors: List[str] = Field(default_factory=list)
