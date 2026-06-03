from sqlalchemy import Column,Integer,String,Text,DateTime,ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo


class NursingNote(Base):

    __tablename__ = "nursing_notes"

    id = Column(Integer,primary_key=True,index=True)

    appointment_id = Column(Integer,ForeignKey("appointments.id"),nullable=False)
    patient_id = Column(Integer,nullable=False)

    nurse_id = Column(Integer,ForeignKey("users.id"),nullable=False)
    symptoms = Column(Text,nullable=True)
    treatment_response = Column(Text,nullable=True)
    additional_notes = Column(Text,nullable=True)
    status = Column(String,default="active",nullable=False)

    created_at = Column(DateTime(timezone=True),
            default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
    )

    appointment = relationship("Appointment")
    nurse = relationship("User",foreign_keys=[nurse_id])