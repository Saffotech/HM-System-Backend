"""Requests for the patient Profile tab."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.patient_portal_schema import PatientPayAppointment

BLOOD_GROUPS = frozenset({"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"})


class PatientProfileUpdate(BaseModel):
    """Fields a patient may change themselves.

    Name, date of birth, gender, UHID and email are not here on purpose.
    The hospital owns them, so a request that sends one is rejected (422).
    Send only the fields that changed. Send null or "" to clear an optional one.
    """

    model_config = ConfigDict(extra="forbid")

    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    state: Optional[str] = Field(None, max_length=100)
    blood_group: Optional[str] = Field(None, max_length=5)
    allergies: Optional[str] = Field(None, max_length=1000)
    insurance_policy_no: Optional[str] = Field(None, max_length=100)
    emergency_contact_name: Optional[str] = Field(None, max_length=120)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact_relation: Optional[str] = Field(None, max_length=50)

    @field_validator("blood_group")
    @classmethod
    def blood_group_is_known(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if normalized not in BLOOD_GROUPS:
            raise ValueError("Blood group must be one of: " + ", ".join(sorted(BLOOD_GROUPS)))
        return normalized


class PatientPayVisit(PatientPayAppointment):
    """Pay an OPD bill by its visit id. Same fields as paying by appointment."""
