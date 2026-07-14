"""Nurse patient overview — composed clinical snapshot for one patient."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.nurse_emergency_alert import AlertStatus, EmergencyAlert
from Models.nurse_medication_administration import (
    MedicationAdministration,
    MedicationStatus,
)
from Models.nurse_nursing_notes import NursingNote
from Models.opd_billing import Bed
from Models.patient import Patient
from Services import doctor_helpers as h
from Services.nurse_dashboard_service import (
    _latest_vitals_map,
    _pending_medication_counts,
    _vital_summary,
)


def get_nurse_patient_overview_service(
    db: Session,
    patient_id: int,
    *,
    notes_limit: int = 5,
    alerts_limit: int = 10,
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active.is_(True))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    bed = (
        db.query(Bed)
        .filter(Bed.patient_id == patient.id, Bed.status == "occupied")
        .order_by(Bed.admitted_at.desc())
        .first()
    )

    vitals_map = _latest_vitals_map(db, [patient.id])
    pending_map = _pending_medication_counts(db, [patient.id])

    notes = (
        db.query(NursingNote)
        .filter(NursingNote.patient_id == patient.id)
        .order_by(NursingNote.created_at.desc())
        .limit(max(1, min(notes_limit, 50)))
        .all()
    )

    alerts = (
        db.query(EmergencyAlert)
        .filter(
            EmergencyAlert.patient_id == patient.id,
            EmergencyAlert.status == AlertStatus.ACTIVE,
            EmergencyAlert.is_active.is_(True),
        )
        .order_by(EmergencyAlert.triggered_at.desc())
        .limit(max(1, min(alerts_limit, 50)))
        .all()
    )

    prescription = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc())
        .first()
    )

    medications = []
    if prescription:
        items = (
            db.query(PrescriptionItem)
            .filter(PrescriptionItem.prescription_id == prescription.id)
            .all()
        )
        given_ids = {
            row[0]
            for row in (
                db.query(MedicationAdministration.prescription_item_id)
                .filter(
                    MedicationAdministration.patient_id == patient.id,
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
            medications.append({
                "prescription_item_id": item.id,
                "medicine_name": item.medicine_name,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "instructions": item.instructions,
                "is_given": item.id in given_ids,
            })

    return {
        "success": True,
        "patient": {
            "id": patient.id,
            "patient_uid": patient.patient_uid,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "full_name": h.display_name(patient.first_name, patient.last_name),
            "phone": patient.phone,
            "gender": patient.gender,
            "blood_group": patient.blood_group,
            "allergies": patient.allergies,
        },
        "bed": (
            {
                "bed_id": bed.id,
                "bed_number": bed.bed_number,
                "ward_name": bed.ward_name,
                "department_id": bed.department_id,
                "admitted_at": bed.admitted_at,
            }
            if bed
            else None
        ),
        "last_vitals": _vital_summary(vitals_map.get(patient.id)),
        "pending_medication_count": pending_map.get(patient.id, 0),
        "medications": medications,
        "recent_notes": [
            {
                "id": note.id,
                "symptoms": note.symptoms,
                "treatment_response": note.treatment_response,
                "additional_notes": note.additional_notes,
                "status": note.status.value if note.status else None,
                "created_at": note.created_at,
            }
            for note in notes
        ],
        "active_alerts": [
            {
                "alert_id": alert.id,
                "alert_uid": alert.alert_uid,
                "alert_type": (
                    alert.alert_type.value
                    if hasattr(alert.alert_type, "value")
                    else alert.alert_type
                ),
                "severity": (
                    alert.severity.value
                    if hasattr(alert.severity, "value")
                    else alert.severity
                ),
                "title": alert.title,
                "ward_name": alert.ward_name,
                "bed_number": alert.bed_number,
                "triggered_at": alert.triggered_at,
                "assigned_nurse_id": alert.assigned_nurse_id,
            }
            for alert in alerts
        ],
    }
