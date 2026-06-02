from pydantic import BaseModel
from datetime import datetime
from typing import Optional,List

class PrescriptionItemCreate(BaseModel):

    medicine_name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):

    appointment_id: int
    diagnosis: str
    notes: Optional[str] = None
    items: List[PrescriptionItemCreate]

class PrescriptionItemResponse(BaseModel):

    id : int
    medicine_name : str
    dosage : str
    frequency : str
    duration : str
    instructions : str

    class Config:
        from_attributes = True

class PrescriptionResponse(BaseModel):

    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    diagnosis: str
    notes: Optional[str]     
    created_at: datetime
    updated_at: datetime
    items: List[PrescriptionItemResponse]

    class Config:
        from_attributes = True

