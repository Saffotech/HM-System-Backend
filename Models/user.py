from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key =True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String,nullable=True)
    email = Column(String, unique=True,nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))