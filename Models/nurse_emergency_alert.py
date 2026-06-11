from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column,Integer,String,DateTime,ForeignKey,Text,Boolean,Enum
from sqlalchemy.orm import relationship
from database import Base
import enum

def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))

# ==========================================================
# ALERT TYPE
# ==========================================================

class AlertType(str, enum.Enum):
    LOW_BP = "low_bp"
    HIGH_BP = "high_bp"
    HIGH_FEVER = "high_fever"
    CARDIAC = "cardiac"
    LOW_SPO2 = "low_spo2"
    OVERDUE_MEDICATION = "overdue_medication"
    MANUAL = "manual"
    OTHER = "other"

# ==========================================================
# ALERT SEVERITY
# ==========================================================

class AlertSeverity(str, enum.Enum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==========================================================
# ALERT STATUS
# ==========================================================

class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


# ==========================================================
# EMERGENCY ALERTS
# ==========================================================

class EmergencyAlert(Base):

    __tablename__ = "emergency_alerts"

    id = Column(Integer,primary_key=True,index=True)
    alert_uid = Column(String(50),unique=True,nullable=False,index=True)
    patient_id = Column(Integer,ForeignKey("patients.id"),nullable=False,index=True)
    alert_type = Column(Enum(AlertType),nullable=False,index=True)
    severity = Column(Enum(AlertSeverity),nullable=False,index=True)
    title = Column(String(255),nullable=True)
    description = Column(Text,nullable=True)
    ward_name = Column(String(100),nullable=True,index=True)
    bed_number = Column(String(50),nullable=True)

    status = Column(Enum(AlertStatus),nullable=False,default=AlertStatus.ACTIVE,
                    index=True)
    is_active = Column(Boolean,default=True,nullable=False)
    triggered_by = Column(Integer,ForeignKey("users.id"),nullable=True)
    triggered_at = Column(DateTime(timezone=True),default=_now,nullable=False,
                          index=True)
    assigned_nurse_id = Column(Integer,ForeignKey("users.id"),nullable=True,index=True)
    resolved_by = Column(Integer,ForeignKey("users.id"),nullable=True)
    resolved_at = Column(DateTime(timezone=True),nullable=True)

    resolution_notes = Column(
        Text,
        nullable=True
    )

    escalated = Column(
        Boolean,
        default=False,
        nullable=False
    )

    escalated_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    escalated_to_doctor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    escalation_notes = Column(
        Text,
        nullable=True
    )

    vital_id = Column(
        Integer,
        ForeignKey("patient_vitals.id"),
        nullable=True,
        index=True
    )

    medication_administration_id = Column(
        Integer,
        ForeignKey("medication_administrations.id"),
        nullable=True,
        index=True
    )

    assigned_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=_now,
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False
    )

    # ======================================================
    # RELATIONSHIPS
    # ======================================================

    patient = relationship(
        "Patient"
    )

    triggered_by_user = relationship(
        "User",
        foreign_keys=[triggered_by]
    )

    assigned_nurse = relationship(
        "User",
        foreign_keys=[assigned_nurse_id]
    )

    resolved_by_user = relationship(
        "User",
        foreign_keys=[resolved_by]
    )

    escalated_doctor = relationship(
        "User",
        foreign_keys=[escalated_to_doctor_id]
    )

    vital = relationship(
        "PatientVitals"
    )

    medication_administration = relationship(
        "MedicationAdministration"
    )

