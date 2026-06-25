from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from Models.nurse_emergency_alert import AlertSeverity, AlertType
from Models.nurse_medication_administration import (
    MedicationAdministration,
    MedicationStatus,
)
from Models.nurse_patient_vitals import PatientVitals
from Services.nurse_emergency_alert_service import create_auto_alert_service

IST = ZoneInfo("Asia/Kolkata")


def _parse_blood_pressure(
    blood_pressure: str | None,
) -> tuple[int, int] | None:
    if not blood_pressure:
        return None

    parts = blood_pressure.strip().replace(" ", "").split("/")
    if len(parts) != 2:
        return None

    try:
        systolic = int(parts[0])
        diastolic = int(parts[1])
    except ValueError:
        return None

    return systolic, diastolic


def _is_high_fever(temperature: float | None) -> bool:
    if temperature is None:
        return False

    # Accept either Celsius (>= 39.4) or Fahrenheit (>= 103).
    if temperature >= 103:
        return True

    return temperature >= 39.4


def evaluate_vital_alert_specs(
    vital: PatientVitals,
    *,
    mark_critical: bool = False,
) -> list[dict]:
    specs: list[dict] = []

    bp = _parse_blood_pressure(vital.blood_pressure)
    if bp:
        systolic, diastolic = bp
        if systolic < 90 or diastolic < 60:
            specs.append({
                "alert_type": AlertType.LOW_BP,
                "severity": AlertSeverity.HIGH,
                "title": "Low blood pressure",
                "description": (
                    f"BP {vital.blood_pressure} "
                    f"(systolic < 90 or diastolic < 60)"
                ),
            })
        elif systolic > 180 or diastolic > 120:
            specs.append({
                "alert_type": AlertType.HIGH_BP,
                "severity": AlertSeverity.HIGH,
                "title": "High blood pressure",
                "description": (
                    f"BP {vital.blood_pressure} "
                    f"(systolic > 180 or diastolic > 120)"
                ),
            })

    if _is_high_fever(vital.temperature):
        specs.append({
            "alert_type": AlertType.HIGH_FEVER,
            "severity": AlertSeverity.HIGH,
            "title": "High fever",
            "description": (
                f"Temperature {vital.temperature} "
                f"(threshold: 39.4 C / 103 F)"
            ),
        })

    if (
        vital.oxygen_saturation is not None
        and vital.oxygen_saturation < 90
    ):
        specs.append({
            "alert_type": AlertType.LOW_SPO2,
            "severity": AlertSeverity.CRITICAL,
            "title": "Low oxygen saturation",
            "description": (
                f"SpO2 {vital.oxygen_saturation}% (below 90%)"
            ),
        })

    if vital.heart_rate is not None and (
        vital.heart_rate < 50 or vital.heart_rate > 120
    ):
        specs.append({
            "alert_type": AlertType.CARDIAC,
            "severity": AlertSeverity.HIGH,
            "title": "Abnormal heart rate",
            "description": (
                f"Heart rate {vital.heart_rate} BPM "
                f"(normal range 50-120)"
            ),
        })

    if mark_critical:
        specs.append({
            "alert_type": AlertType.MANUAL,
            "severity": AlertSeverity.CRITICAL,
            "title": "Nurse marked patient critical",
            "description": (
                vital.observation_notes
                or "Marked critical while recording vitals"
            ),
        })

    return specs


def process_vital_alerts(
    db: Session,
    vital: PatientVitals,
    nurse_id: int,
    *,
    mark_critical: bool = False,
) -> list[int]:
    alert_ids: list[int] = []

    for spec in evaluate_vital_alert_specs(
        vital,
        mark_critical=mark_critical,
    ):
        alert = create_auto_alert_service(
            db=db,
            patient_id=vital.patient_id,
            alert_type=spec["alert_type"],
            severity=spec["severity"],
            title=spec["title"],
            description=spec["description"],
            vital_id=vital.id,
            triggered_by=nurse_id,
        )
        if alert:
            alert_ids.append(alert.id)

    return alert_ids


def _is_medication_overdue(
    administration: MedicationAdministration,
) -> bool:
    if administration.status != MedicationStatus.MISSED:
        return False

    if administration.scheduled_time is None:
        return True

    scheduled = administration.scheduled_time
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=IST)

    return scheduled <= datetime.now(IST)


def process_medication_missed_alert(
    db: Session,
    administration: MedicationAdministration,
    nurse_id: int,
) -> int | None:
    if not _is_medication_overdue(administration):
        return None

    medicine = administration.medicine_name
    description = f"{medicine} marked as missed"
    if administration.scheduled_time:
        description += (
            f" (scheduled {administration.scheduled_time})"
        )

    alert = create_auto_alert_service(
        db=db,
        patient_id=administration.patient_id,
        alert_type=AlertType.OVERDUE_MEDICATION,
        severity=AlertSeverity.MEDIUM,
        title="Overdue medication",
        description=description,
        medication_administration_id=administration.id,
        triggered_by=nurse_id,
    )

    return alert.id if alert else None


def get_active_alerts_text_for_patient(
    db: Session,
    patient_id: int,
) -> str | None:
    from Models.nurse_emergency_alert import (
        EmergencyAlert,
        AlertStatus,
    )

    alerts = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.patient_id == patient_id,
            EmergencyAlert.status == AlertStatus.ACTIVE,
        )
        .order_by(EmergencyAlert.triggered_at.desc())
        .all()
    )

    if not alerts:
        return None

    parts = []
    for alert in alerts:
        label = alert.title or alert.alert_type.value.replace("_", " ")
        parts.append(f"{label} ({alert.severity.value})")

    return "; ".join(parts)
