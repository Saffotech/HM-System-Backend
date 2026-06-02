from sqlalchemy import Column,Integer,String,Date,DateTime,Boolean,ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo


class PatientQueue(Base):

    __tablename__ = "patient_queue"

    id = Column(Integer,primary_key=True,index=True)

    appointment_id = Column(Integer,ForeignKey("appointments.id"),nullable=False)


    patient_id = Column(Integer,nullable=False)
    patient_name = Column(String,nullable=False)
    patient_uhid = Column(String,nullable=False)

    doctor_id = Column(Integer,ForeignKey("users.id"),nullable=False)

    token_number = Column(Integer,nullable=False)
    queue_date = Column(Date,nullable=False)
    status = Column(String,
        default="waiting",
        nullable=False
    )
    priority = Column(String,default="normal",nullable=False)
    is_current = Column(Boolean,default=False)

    queue_entered_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    consultation_started_at = Column(DateTime(timezone=True),nullable=True)

    consultation_completed_at = Column(DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    appointment = relationship("Appointment")
    doctor = relationship("User",foreign_keys=[doctor_id])