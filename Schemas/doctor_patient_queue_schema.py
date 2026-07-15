from pydantic import BaseModel
from datetime import date
from typing import Optional


class CompleteConsultationSchema(BaseModel):
    symptoms: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
