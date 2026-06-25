from datetime import date, datetime

from typing import Optional



from pydantic import BaseModel, ConfigDict, Field



from Schemas.common_schema import PaginatedResponse





# ==========================================================

# Today queue

# ==========================================================



class NurseDashboardQueueItem(BaseModel):

    id: int

    appointment_id: int

    patient_id: int

    patient_name: str

    patient_uid: str

    patient_phone: Optional[str] = None

    appointment_uid: Optional[str] = None

    doctor_id: int

    token_number: int

    queue_date: date

    status: str

    priority: str

    is_current: bool = False

    queue_entered_at: Optional[datetime] = None

    consultation_started_at: Optional[datetime] = None

    consultation_completed_at: Optional[datetime] = None

    created_at: Optional[datetime] = None



    model_config = ConfigDict(from_attributes=True, populate_by_name=True)





class NurseDashboardQueueResponse(PaginatedResponse[NurseDashboardQueueItem]):

    pass





# ==========================================================

# Bed-assigned patients

# ==========================================================



class NurseDashboardBedPatientLastVitals(BaseModel):

    vital_id: int

    recorded_at: datetime

    temperature: Optional[float] = None

    blood_pressure: Optional[str] = None

    heart_rate: Optional[int] = None

    oxygen_saturation: Optional[int] = None

    status: Optional[str] = None





class NurseDashboardBedPatientItem(BaseModel):

    patient_id: int

    patient_name: str

    patient_uid: str

    patient_phone: Optional[str] = None



    bed_id: int

    bed_number: str

    ward_name: str

    department_id: Optional[int] = None

    department_name: Optional[str] = None



    admitted_at: Optional[datetime] = None



    last_vitals: Optional[NurseDashboardBedPatientLastVitals] = None

    pending_medication_count: int = 0





class NurseDashboardBedPatientListResponse(PaginatedResponse[NurseDashboardBedPatientItem]):

    pass





class NurseDashboardBedPatientSummaryResponse(BaseModel):

    success: bool = True

    occupied_count: int


