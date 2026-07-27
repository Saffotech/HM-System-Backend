"""Pydantic schemas for Nurse Workforce (shifts + roster)."""
from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NurseWorkforceShiftCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    start_time: time
    end_time: time
    grace_minutes: int = Field(15, ge=0, le=180)
    color: Optional[str] = Field("#3B82F6", max_length=20)
    is_active: bool = True
    is_template: bool = False
    weekly_mask: Optional[str] = Field("1111100", max_length=20)
    notes: Optional[str] = None


class NurseWorkforceShiftUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    grace_minutes: Optional[int] = Field(None, ge=0, le=180)
    color: Optional[str] = None
    is_active: Optional[bool] = None
    is_template: Optional[bool] = None
    weekly_mask: Optional[str] = None
    notes: Optional[str] = None


class NurseWorkforceRosterCreate(BaseModel):
    nurse_id: int = Field(..., ge=1)
    shift_id: int = Field(..., ge=1)
    department_id: Optional[int] = Field(None, ge=1)
    roster_date: date
    status: str = "scheduled"
    notes: Optional[str] = None


class NurseWorkforceRosterBulkCreate(BaseModel):
    nurse_ids: List[int] = Field(..., min_length=1)
    shift_id: int = Field(..., ge=1)
    department_id: Optional[int] = Field(None, ge=1)
    dates: List[date] = Field(..., min_length=1)
    notes: Optional[str] = None


class NurseWorkforceShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    start_time: time
    end_time: time
    grace_minutes: int
    color: Optional[str] = None
    is_active: bool
    is_template: bool
    weekly_mask: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
