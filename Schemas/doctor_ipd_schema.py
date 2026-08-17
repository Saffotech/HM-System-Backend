from typing import Optional, Union

from pydantic import BaseModel, Field

from Schemas.common_schema import PaginatedResponse, PaginationParams
from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema



class DoctorIpdAdmissionItem(BaseModel):
    """Doctor-facing IPD row (same shape as admission_to_dict)."""

    id: Union[int, str]
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_age: Optional[Union[int, str]] = None
    patient_gender: Optional[Union[str, int]] = None
    patient_uid: str
    registration_source: str
    doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    scheduled_at: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_type: str
    encounter_type: str = "IPD"
    admission_id: Optional[int] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    status: str
    reason: Optional[str] = None
    symptoms: Optional[str] = None
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    follow_up: Optional[str] = None
    admitted_at: Optional[str] = None
    discharged_at: Optional[str] = None
    created_at: Optional[str] = None


class DoctorIpdAdmissionListResponse(PaginatedResponse[DoctorIpdAdmissionItem]):
    pass


class DoctorIpdConsultationSaveRequest(BaseModel):
    clinical: CompleteConsultationSchema = Field(default_factory=CompleteConsultationSchema)


class DoctorIpdVisitOut(BaseModel):
    id: int
    admission_id: int
    doctor_id: int
    visited_at: Optional[str] = None
    charge: float = 0
    notes: Optional[str] = None


class DoctorIpdConsultationSaveResponse(BaseModel):
    success: bool = True
    message: str = "IPD consultation saved"
    admission: DoctorIpdAdmissionItem
    visit: DoctorIpdVisitOut


PaginationSchema = PaginationParams
