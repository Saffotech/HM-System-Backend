from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    first_name      = Column(String, nullable=False)
    last_name       = Column(String, nullable=True)
    username        = Column(String, nullable=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    password        = Column(String, nullable=False)

    # RBAC — role_id replaces role string
    role_id         = Column(Integer, ForeignKey("roles.id"), nullable=True)
    role_obj        = relationship("Role")
    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True
    )

    department = relationship("Department")

    specialization = Column(String(120), nullable=True)

    # profile
    gender          = Column(Integer, nullable=True)
    phone           = Column(String(20), nullable=True)
    phone_code      = Column(String(10), nullable=True)
    address         = Column(String, nullable=True)
    city            = Column(String(100), nullable=True)
    state           = Column(String(100), nullable=True)
    profile_picture = Column(String, nullable=True)

    # tracking
    last_login      = Column(DateTime(timezone=True), nullable=True)
    login_count     = Column(Integer, default=0)
    deleted_at      = Column(DateTime(timezone=True), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

