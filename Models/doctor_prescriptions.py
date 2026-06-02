from sqlalchemy import Column, Integer, String, DateTime, ForeignKey,Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from zoneinfo import ZoneInfo

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True , index=True)
    appointment_id = Column(Integer,ForeignKey("appointments.id"),
                            nullable=False,unique=True)
    patient_id = Column(Integer,nullable=False)
    patient_name = Column(String,nullable=True)

    doctor_id = Column(Integer, ForeignKey('users.id'),nullable=False)
    diagnosis = Column(String , nullable=False)
    notes = Column(String,nullable=True)

    created_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    updated_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        ),
        onupdate=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )
    appointment = relationship("Appointment")

    doctor = relationship("User", foreign_keys=[doctor_id])

    items = relationship("PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan"
    )


class PrescriptionItem(Base):

    __tablename__ = "prescription_items"

    id = Column(Integer,primary_key=True,index=True)

    prescription_id = Column(Integer,ForeignKey("prescriptions.id"),nullable=False)
    medicine_name = Column(String,nullable=False)
    dosage = Column(String,nullable=False)
    frequency = Column(String,nullable=False)
    duration = Column(Integer,nullable=False)
    instructions = Column(Text,nullable=True)

    created_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    updated_at = Column(DateTime(timezone=True),
        default=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        ),
        onupdate=lambda: datetime.now(
            ZoneInfo("Asia/Kolkata")
        )
    )

    prescription = relationship("Prescription",
        back_populates="items"
    )