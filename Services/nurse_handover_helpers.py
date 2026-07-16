"""Internal helpers for nurse shift handover."""
from __future__ import annotations

from datetime import datetime, date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Constants.constants import Role as RoleEnum
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.nurse_medication_administration import (
    MedicationAdministration,
    MedicationStatus,
)
from Models.nurse_nursing_notes import NursingNote
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_handover import ShiftHandover
from Models.opd_billing import Bed
from Models.patient import Patient
from Models.user import User
from Services import nurse_helpers as nh
from Services.nurse_emergency_alert_triggers import (
    get_active_alerts_text_for_patient,
)


def _now():
    return nh.now_ist()


def _generate_handover_uid(db: Session):
    current_year = datetime.now().year
    last_record = (
        db.query(ShiftHandover)
        .order_by(ShiftHandover.id.desc())
        .first()
    )
    next_number = 1
    if last_record:
        next_number = last_record.id + 1

    return f"HO-{current_year}-{str(next_number).zfill(6)}"


def _user_display_name(user: User | None) -> str | None:
    return nh.user_display_name(user)


def _is_nurse_user(user: User | None) -> bool:
    if not user or not user.role_obj:
        return False
    return user.role_obj.name == RoleEnum.NURSE


def _format_vitals_summary(vital: PatientVitals) -> str:
    parts = []
    if vital.temperature is not None:
        parts.append(f"Temp {vital.temperature}")
    if vital.blood_pressure:
        parts.append(f"BP {vital.blood_pressure}")
    if vital.heart_rate is not None:
        parts.append(f"HR {vital.heart_rate}")
    if vital.respiratory_rate is not None:
        parts.append(f"RR {vital.respiratory_rate}")
    if vital.oxygen_saturation is not None:
        parts.append(f"SpO2 {vital.oxygen_saturation}")
    if vital.blood_sugar is not None:
        parts.append(f"BS {vital.blood_sugar}")
    if vital.pain_level is not None:
        parts.append(f"Pain {vital.pain_level}/10")
    if vital.observation_notes:
        parts.append(vital.observation_notes.strip())

    recorded = (
        vital.recorded_at.strftime("%Y-%m-%d %H:%M")
        if vital.recorded_at
        else "unknown time"
    )
    if not parts:
        return f"Last vitals recorded at {recorded}"
    return f"Last vitals ({recorded}): " + ", ".join(parts)


def _build_patient_care_snapshot(
    db: Session,
    patient_id: int,
    shift_date: date | None = None,
) -> dict:
    """Auto-fill handover patient fields from clinical work already done."""

    day = shift_date or _now().date()
    day_start = datetime(
        day.year,
        day.month,
        day.day,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    day_end = day_start + timedelta(days=1)

    latest_vital = (
        db.query(PatientVitals)
        .filter(PatientVitals.patient_id == patient_id)
        .order_by(PatientVitals.recorded_at.desc())
        .first()
    )

    latest_note = (
        db.query(NursingNote)
        .filter(NursingNote.patient_id == patient_id)
        .order_by(NursingNote.created_at.desc())
        .first()
    )

    summary_parts: list[str] = []
    if latest_vital:
        summary_parts.append(_format_vitals_summary(latest_vital))
    if latest_note:
        note_bits = [
            bit.strip()
            for bit in [
                latest_note.symptoms,
                latest_note.treatment_response,
                latest_note.additional_notes,
            ]
            if bit and bit.strip()
        ]
        if note_bits:
            summary_parts.append("Nursing note: " + "; ".join(note_bits))

    administrations = (
        db.query(MedicationAdministration)
        .filter(
            MedicationAdministration.patient_id == patient_id,
            MedicationAdministration.administered_at >= day_start,
            MedicationAdministration.administered_at < day_end,
        )
        .order_by(MedicationAdministration.administered_at.desc())
        .all()
    )

    given_parts = []
    issue_parts = []
    given_item_ids: set[int] = set()

    for admin in administrations:
        label = admin.medicine_name
        if admin.dosage:
            label = f"{label} {admin.dosage}"
        if admin.status == MedicationStatus.GIVEN:
            given_parts.append(label)
            given_item_ids.add(admin.prescription_item_id)
        elif admin.status in (
            MedicationStatus.MISSED,
            MedicationStatus.DELAYED,
            MedicationStatus.REFUSED,
        ):
            issue_parts.append(
                f"{label} ({admin.status.value})"
            )

    if given_parts:
        # Keep unique while preserving order
        unique_given = list(dict.fromkeys(given_parts))
        summary_parts.append(
            "Meds given this shift: " + ", ".join(unique_given)
        )

    prescription = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .first()
    )

    pending_parts = list(dict.fromkeys(issue_parts))
    instruction_parts: list[str] = []

    if prescription:
        if prescription.notes and prescription.notes.strip():
            instruction_parts.append(prescription.notes.strip())
        if prescription.diagnosis and prescription.diagnosis.strip():
            instruction_parts.append(
                f"Diagnosis: {prescription.diagnosis.strip()}"
            )

        items = (
            db.query(PrescriptionItem)
            .filter(PrescriptionItem.prescription_id == prescription.id)
            .all()
        )

        ever_given_ids = {
            row[0]
            for row in (
                db.query(MedicationAdministration.prescription_item_id)
                .filter(
                    MedicationAdministration.patient_id == patient_id,
                    MedicationAdministration.status == MedicationStatus.GIVEN,
                    MedicationAdministration.prescription_item_id.in_(
                        [item.id for item in items] or [-1]
                    ),
                )
                .distinct()
                .all()
            )
        }

        for item in items:
            if item.instructions and item.instructions.strip():
                instruction_parts.append(
                    f"{item.medicine_name}: {item.instructions.strip()}"
                )
            if item.id not in ever_given_ids and item.id not in given_item_ids:
                pending_label = item.medicine_name
                if item.dosage:
                    pending_label = f"{pending_label} {item.dosage}"
                if item.frequency:
                    pending_label = f"{pending_label} ({item.frequency})"
                pending_parts.append(pending_label)

    critical_alerts = get_active_alerts_text_for_patient(db, patient_id)

    task_parts: list[str] = []
    if pending_parts:
        task_parts.append(
            f"{len(list(dict.fromkeys(pending_parts)))} medication(s) pending/attention"
        )
    if critical_alerts:
        task_parts.append("Review active critical alerts")
    if not latest_vital or (
        latest_vital.recorded_at and latest_vital.recorded_at < day_start
    ):
        task_parts.append("Vitals due / outdated")

    return {
        "patient_summary": " | ".join(summary_parts) if summary_parts else None,
        "medication_pending": (
            "; ".join(dict.fromkeys(pending_parts)) if pending_parts else None
        ),
        "doctor_instructions": (
            "; ".join(dict.fromkeys(instruction_parts))
            if instruction_parts
            else None
        ),
        "critical_alerts": critical_alerts,
        "pending_tasks": "; ".join(task_parts) if task_parts else None,
    }

# ==========================================================
# CREATE HANDOVER
# ==========================================================

