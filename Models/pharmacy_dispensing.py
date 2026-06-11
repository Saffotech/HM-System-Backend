from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Dispensing(Base):
    __tablename__ = "dispensings"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False, index=True)
    dispensed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity_dispensed = Column(Integer, nullable=False)
    remarks = Column(String, nullable=True)
    batch_number = Column(String, nullable=True)
    status = Column(String, default="dispensed")
    dispensed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
    )

    prescription = relationship("Prescription")
    pharmacist = relationship("User", foreign_keys=[dispensed_by])
