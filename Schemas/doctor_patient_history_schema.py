from typing import Optional



from pydantic import BaseModel, Field



from Schemas.common_schema import PaginatedResponse, PaginationParams





class PatientHistoryItem(BaseModel):

    """Completed visit row for doctor patient history (OPD appointment + patient)."""



    id: int

    appointment_uid: str

    patient_id: int

    patient_name: str

    patient_uid: str

    patient_phone: str

    patient_age: Optional[int] = None

    patient_gender: Optional[str | int] = None

    doctor_id: int

    department_id: int

    scheduled_at: Optional[str] = None

    appointment_date: Optional[str] = None

    appointment_time: Optional[str] = None

    appointment_type: str

    status: str

    reason: Optional[str] = None

    notes: Optional[str] = None





class PatientHistoryListResponse(PaginatedResponse[PatientHistoryItem]):

    pass





class PatientHistoryDetailResponse(BaseModel):

    success: bool = True

    patient_history: list[PatientHistoryItem]





# Re-export shared pagination params for router Depends()

PaginationSchema = PaginationParams


