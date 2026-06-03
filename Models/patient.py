from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True, index=True)
    patient_uid = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    blood_group = Column(String(5), nullable=True)
    phone = Column(String(15), nullable=False, index=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    state = Column(String(100), nullable=True)
    aadhaar_number = Column(String(14), nullable=True)
    emergency_contact_name = Column(String, nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    allergies = Column(String, nullable=True)
    insurance_policy_no = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    registered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

class OpdVisit(Base):
    __tablename__ = "opd_visits"

    id = Column(Integer, primary_key=True, index=True)

    bill_number = Column(String, nullable=False, unique=True)
    token_number = Column(String, nullable=False, unique=True)

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    registration_fee    = Column(Float, default=200.0)
    consultation_fee    = Column(Float, default=800.0)
    subtotal            = Column(Float, default=0.0)
    gst_percent         = Column(Float, default=5.0)
    gst_amount          = Column(Float, default=0.0)
    grand_total         = Column(Float, default=0.0)

    payment_status   = Column(String, default="pending")
    payment_mode     = Column(String, nullable=True)
    paid_amount      = Column(Float, nullable=True)
    balance_due      = Column(Float, default=0.0)
    paid_at          = Column(DateTime(timezone=True), nullable=True)

    status           = Column(String, default="registered")

    registered_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    visit_date       = Column(DateTime(timezone=True),
                          default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))
    created_at       = Column(DateTime(timezone=True),
                          default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))
