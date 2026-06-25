from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import relationship

from database import Base

from datetime import datetime
from zoneinfo import ZoneInfo
import enum


IST = ZoneInfo("Asia/Kolkata")


class ParameterFlag(str, enum.Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"


class LabResult(Base):

    __tablename__ = "lab_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # One report per lab order
    lab_test_order_id = Column(
        Integer,
        ForeignKey(
            "lab_test_orders.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True
    )

    # Lab technician who uploaded report
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    sample_collected_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    test_performed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # PDF / Image / URL path
    report_file = Column(
        String(500),
        nullable=True
    )

    remarks = Column(
        Text,
        nullable=True
    )

    file_name = Column(
        String(255),
        nullable=True
    )

    file_type = Column(
        String(100),
        nullable=True
    )

    file_size = Column(
        Integer,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(IST),
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST),
        nullable=False
    )

    # Relationships

    lab_order = relationship(
        "LabTestOrder",
        back_populates="lab_result"
    )

    uploaded_by_user = relationship(
        "User",
        foreign_keys=[uploaded_by]
    )

    parameters = relationship(
        "LabResultParameter",
        back_populates="lab_result",
        cascade="all, delete-orphan"
    )


class LabResultParameter(Base):

    __tablename__ = "lab_result_parameters"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    lab_result_id = Column(
        Integer,
        ForeignKey(
            "lab_results.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    parameter_name = Column(
        String(255),
        nullable=False
    )

    value = Column(
        String(255),
        nullable=True
    )

    unit = Column(
        String(100),
        nullable=True
    )

    normal_range = Column(
        String(100),
        nullable=True
    )

    flag = Column(
        Enum(ParameterFlag),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(IST),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(IST),
        onupdate=lambda: datetime.now(IST),
        nullable=False
    )

    # Relationships

    lab_result = relationship(
        "LabResult",
        back_populates="parameters"
    )