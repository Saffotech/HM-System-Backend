from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from Models.nurse_medication_administration import MedicationStatus


class MedicationAdministrationCreate(BaseModel):
    prescription_item_id: int
    status: MedicationStatus
    remarks: Optional[str] = None
    scheduled_time: Optional[datetime] = None


class MedicationAdministrationUpdate(BaseModel):
    status: MedicationStatus
    remarks: Optional[str] = None


class MedicationAdministrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prescription_item_id: int
    patient_id: int
    patient_uid: Optional[str] = None
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    status: str
    remarks: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    administered_at: datetime


class PatientMedicationItem(BaseModel):
    prescription_item_id: int
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[int] = None
    instructions: Optional[str] = None


class PatientMedicationResponse(BaseModel):
    patient_id: int
    patient_uid: Optional[str] = None
    patient_name: str
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    medications: List[PatientMedicationItem]


class MedicationPatientListItem(BaseModel):
    patient_id: int
    patient_name: str
    patient_uid: Optional[str] = None
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    medicine_count: int = 0


class MedicationHistoryResponse(BaseModel):
    administration_id: int
    medicine_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    status: str
    bed_number: Optional[str] = None
    ward_name: Optional[str] = None
    remarks: Optional[str] = None
    administered_at: datetime


class MedicationMessageResponse(BaseModel):
    message: str = Field(..., min_length=1)
