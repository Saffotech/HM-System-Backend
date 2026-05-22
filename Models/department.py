from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Department(Base):
    __tablename__ = "departments"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)   # Cardiology, Ortho, General
    code        = Column(String(10), nullable=True) # CARD, ORTH, GEN
    description = Column(String, nullable=True)
    is_active   = Column(Boolean, default=True)

class Specialization(Base):
    __tablename__ = "specializations"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)  # Cardiologist, Orthopedist
    department_id   = Column(Integer, ForeignKey("departments.id"), nullable=False)
    is_active       = Column(Boolean, default=True)