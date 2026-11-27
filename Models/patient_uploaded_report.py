"""Reports a patient uploads themselves (My Uploads).

Hospital lab PDFs stay in lab_results. This table is only for files the
patient adds from home: old prescriptions, external labs, and similar.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from Models.tenant import TenantScoped

IST = ZoneInfo("Asia/Kolkata")


class PatientUploadedReport(TenantScoped):
    __tablename__ = "patient_uploaded_reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    report_file = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(IST),
        nullable=False,
        index=True,
    )

    patient = relationship("Patient", foreign_keys=[patient_id])
    uploaded_by_user = relationship("User", foreign_keys=[uploaded_by_user_id])
