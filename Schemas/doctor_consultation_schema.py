from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field

from Schemas.doctor_patient_queue_schema import CompleteConsultationSchema


class SaveConsultationRequest(BaseModel):
    appointment_id: int
    clinical: CompleteConsultationSchema = Field(default_factory=CompleteConsultationSchema)


class ConsultationQueueSummary(BaseModel):
    id: int
    status: str
    appointment_id: int
    token_number: Optional[int] = None

    class Config:
        from_attributes = True


class ConsultationAppointmentSummary(BaseModel):
    id: int
    appointment_uid: str
    status: str
    patient_id: int
    patient_uid: str
    patient_name: str
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    symptoms: Optional[str] = None
    follow_up_date: Optional[date] = None


class SaveConsultationResponse(BaseModel):
    success: bool = True
    message: str = "Consultation saved"
    appointment: dict[str, Any]
    queue: dict[str, Any]


class ConsultationContextResponse(BaseModel):
    success: bool = True
    appointment: dict[str, Any]
    queue: Optional[dict[str, Any]] = None
    prescriptions: list[dict[str, Any]] = Field(default_factory=list)
    lab_orders: list[dict[str, Any]] = Field(default_factory=list)
