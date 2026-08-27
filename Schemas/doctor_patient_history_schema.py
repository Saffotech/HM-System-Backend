from typing import Optional, Union

from pydantic import BaseModel, Field

from Schemas.common_schema import PaginatedResponse, PaginationParams


class PatientHistoryItem(BaseModel):
    """Completed OPD visit or discharged IPD stay for doctor patient history."""

    id: Union[int, str]
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_uid: str
    registration_source: str
    patient_phone: str
    patient_age: Optional[Union[int, str]] = None
    patient_gender: Optional[Union[str, int]] = None
    doctor_id: Optional[int] = None
    department_id: Optional[int] = None
    scheduled_at: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_type: str
    encounter_type: Optional[str] = None
    admission_id: Optional[int] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    status: str
    reason: Optional[str] = None
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    follow_up: Optional[str] = None
    admitted_at: Optional[str] = None
    discharged_at: Optional[str] = None
    nurse_id: Optional[int] = None
    nurse_name: Optional[str] = None


class PatientHistoryListResponse(PaginatedResponse[PatientHistoryItem]):
    pass


class PatientHistoryDetailResponse(PaginatedResponse[PatientHistoryItem]):
    """Paginated visit history for one patient UHID."""

    # Legacy key for existing doctor clients
    patient_history: list[PatientHistoryItem] = Field(default_factory=list)


# Re-export shared pagination params for router Depends()
PaginationSchema = PaginationParams
