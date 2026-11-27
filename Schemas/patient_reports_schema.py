"""Bodies for patient report uploads. Lab report list items are plain dicts."""

from typing import Optional

from pydantic import BaseModel, Field


class PatientUploadReportForm(BaseModel):
    """Title and notes for a file the patient adds under My Uploads."""

    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=1000)
