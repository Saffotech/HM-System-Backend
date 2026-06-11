from Models.nurse_medication_administration import MedicationStatus
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# ==========================================================
# CREATE
# ==========================================================

class MedicationAdministrationCreate(BaseModel):
    prescription_item_id: int
    status: str
    remarks: Optional[str] = None

    scheduled_time: Optional[datetime] = None


# ==========================================================
# UPDATE
# ==========================================================

class MedicationAdministrationUpdate(BaseModel):
    status: str
    remarks: Optional[str] = None


# ==========================================================
# RESPONSE
# ==========================================================

class MedicationAdministrationResponse(BaseModel):

    id: int

    prescription_item_id: int
    patient_id: int

    medicine_name: str

    dosage: Optional[str] = None

    frequency: Optional[str] = None

    bed_number: Optional[str] = None

    ward_name: Optional[str] = None

    status: str

    remarks: Optional[str] = None

    scheduled_time: Optional[datetime] = None

    administered_at: datetime

    class Config:
        from_attributes = True


# ==========================================================
# PATIENT MEDICATIONS
# ==========================================================

class PatientMedicationItem(BaseModel):

    prescription_item_id: int

    medicine_name: str
    dosage: str
    frequency: str

    duration: int

    instructions: Optional[str] = None


class PatientMedicationResponse(BaseModel):

    patient_id: int
    patient_name: str

    bed_number: Optional[str] = None
    ward_name: Optional[str] = None

    medications: List[PatientMedicationItem]


# ==========================================================
# HISTORY
# ==========================================================

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



class MedicationAdministrationCreate(BaseModel):
    prescription_item_id: int
    status: MedicationStatus

class MedicationAdministrationUpdate(BaseModel):
    status: MedicationStatus