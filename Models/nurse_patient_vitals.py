from sqlalchemy import Column,Integer,String,Float,Text,DateTime,ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo


class PatientVitals(Base):

    __tablename__ = "patient_vitals"

    id = Column(Integer,primary_key=True,index=True)

    appointment_id = Column(Integer,ForeignKey("appointments.id"),nullable=False)
    patient_id = Column(Integer,nullable=False)
    recorded_by = Column(Integer,ForeignKey("users.id"),nullable=False)

    temperature = Column(Float,nullable=True)
    blood_pressure = Column(String,nullable=True)
    heart_rate = Column(Integer,nullable=True)
    respiratory_rate = Column(Integer,nullable=True)
    oxygen_saturation = Column(Integer,nullable=True)
    blood_sugar = Column(Float,nullable=True)
    weight = Column(Float,nullable=True)
    pain_level = Column(Integer,nullable=True)
    observation_notes = Column(Text,nullable=True)
    status = Column(String,default="normal",nullable=False)

    recorded_at = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
    )
    
    appointment = relationship("Appointment")
    nurse = relationship("User",foreign_keys=[recorded_by])