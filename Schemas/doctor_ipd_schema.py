from typing import Optional, Union

from pydantic import BaseModel

from Schemas.common_schema import PaginatedResponse, PaginationParams


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


PaginationSchema = PaginationParams
