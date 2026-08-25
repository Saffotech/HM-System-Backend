from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class NurseDoctorVisitCreate(BaseModel):
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    doctor_id: int = Field(..., ge=1)
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def require_appointment_or_patient(self):
        if not self.appointment_id and not self.patient_id:
            raise ValueError("Provide appointment_id or patient_id")
        return self


class NurseDoctorVisitUpdate(BaseModel):
    doctor_id: Optional[int] = Field(None, ge=1)
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None


class NurseDoctorVisitVoidRequest(BaseModel):
    void_reason: str = Field(..., min_length=3, max_length=500)


class NurseDoctorVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_id: int
    doctor_name: str
    visited_at: datetime
    notes: Optional[str] = None
    visit_number: Optional[int] = None
    day_visit_count: Optional[int] = None
    # Populated when patient is IPD-admitted and a billable visit was synced
    admission_id: Optional[int] = None
    charge: Optional[float] = None
    recorded_by: int
    recorded_by_name: str
    created_at: datetime
    updated_by: Optional[int] = None
    updated_by_name: Optional[str] = None
    updated_at: Optional[datetime] = None
    is_voided: bool = False

    model_config = {"from_attributes": True}


class NurseDoctorVisitListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[NurseDoctorVisitResponse]


class NurseDoctorOption(BaseModel):
    id: int
    name: str
    specialization: Optional[str] = None


class NurseDoctorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    doctors: List[NurseDoctorOption]


class DoctorPatientVisitsResponse(BaseModel):
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: Optional[str] = None
    visit_date: date
    visit_count: int
    visits: List[NurseDoctorVisitResponse]
