from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


class Dispensing(Base):
    __tablename__ = "dispensings"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False, index=True)
    dispensed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity_dispensed = Column(Integer, nullable=False)
    remarks = Column(String, nullable=True)
    batch_number = Column(String, nullable=True)
    status = Column(String, default="dispensed")
    dispensed_at = Column(DateTime(timezone=True), default=_now)

    prescription = relationship("Prescription")
    pharmacist = relationship("User", foreign_keys=[dispensed_by])
    items = relationship(
        "DispensingItem",
        back_populates="dispensing",
        cascade="all, delete-orphan",
    )


class DispensingItem(Base):
    __tablename__ = "dispensing_items"

    id = Column(Integer, primary_key=True, index=True)
    dispensing_id = Column(Integer, ForeignKey("dispensings.id"), nullable=False, index=True)
    prescription_item_id = Column(
        Integer,
        ForeignKey("prescription_items.id"),
        nullable=False,
        index=True,
    )
    quantity_dispensed = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    dispensing = relationship("Dispensing", back_populates="items")
    prescription_item = relationship("PrescriptionItem")
