from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class LabTest(Base):
    __tablename__ = "lab_tests"
    __table_args__ = (
        UniqueConstraint(
            "test_name",
            "department_id",
            name="uq_lab_tests_name_department",
        ),
        CheckConstraint("price >= 0", name="ck_lab_tests_price_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    test_name = Column(String(255), nullable=False)
    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=False,
        index=True,
    )
    price = Column(Numeric(10, 2), nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
    )

    department = relationship("Department")
