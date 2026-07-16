from collections import defaultdict
from datetime import date

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from Models.department import Department
from Models.doctor_patient_queue import PatientQueue
from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.nurse_emergency_alert import AlertSeverity, AlertStatus, EmergencyAlert
from Models.nurse_medication_administration import (
    MedicationAdministration,
    MedicationStatus,
)
from Models.nurse_patient_vitals import PatientVitals
from Models.nurse_shift_handover import HandoverStatus, ShiftHandover
from Models.opd_billing import Bed
from Models.patient import Patient
from Services import doctor_helpers as h


def get_nurse_today_queue_service(
    db: Session,
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    status: str | None = None,
    doctor_id: int | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(PatientQueue)
        .filter(PatientQueue.queue_date == date.today())
    )

    if patient_id:
        query = query.filter(PatientQueue.patient_id == patient_id)

    if patient_uid:
        query = query.filter(
            PatientQueue.patient_uhid.ilike(
                f"%{patient_uid.strip()}%"
            )
        )

    if search:
        search_filters = [
            PatientQueue.patient_name.ilike(f"%{search}%"),
            PatientQueue.patient_uhid.ilike(f"%{search}%"),
            PatientQueue.patient_phone.ilike(f"%{search}%"),
            PatientQueue.appointment_uid.ilike(f"%{search}%"),
        ]
        if search.isdigit():
            search_filters.append(PatientQueue.token_number == int(search))
            search_filters.append(PatientQueue.patient_id == int(search))
        query = query.filter(or_(*search_filters))

    if status:
        query = query.filter(PatientQueue.status == status)

    if doctor_id:
        query = query.filter(PatientQueue.doctor_id == doctor_id)

    if priority:
        query = query.filter(PatientQueue.priority == priority)

    total = query.count()

    items = []
    for row in (
        query
        .order_by(
            PatientQueue.priority.desc(),
            PatientQueue.token_number.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    ):
        items.append({
            "id": row.id,
            "appointment_id": row.appointment_id,
            "patient_id": row.patient_id,
            "patient_name": row.patient_name,
            "patient_uid": row.patient_uhid,
            "patient_phone": row.patient_phone,
            "appointment_uid": row.appointment_uid,
            "doctor_id": row.doctor_id,
            "token_number": row.token_number,
            "queue_date": row.queue_date,
            "status": row.status.value if hasattr(row.status, "value") else row.status,
            "priority": row.priority.value if hasattr(row.priority, "value") else row.priority,
            "is_current": row.is_current,
            "queue_entered_at": row.queue_entered_at,
            "consultation_started_at": row.consultation_started_at,
            "consultation_completed_at": row.consultation_completed_at,
            "created_at": row.created_at,
        })

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

 
def _base_bed_patients_query(
    db: Session,
    search: str | None = None,
    ward_name: str | None = None,
    bed_number: str | None = None,
    department_id: int | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
):
    query = (
        db.query(Bed, Patient, Department)
        .join(Patient, Patient.id == Bed.patient_id)
        .outerjoin(Department, Department.id == Bed.department_id)
        .filter(
            Bed.status == "occupied",
            Bed.patient_id.isnot(None),
            Patient.is_active.is_(True),
        )
    )

    if ward_name:
        query = query.filter(
            Bed.ward_name.ilike(f"%{ward_name.strip()}%")
        )

    if bed_number:
        query = query.filter(
            Bed.bed_number.ilike(f"%{bed_number.strip()}%")
        )

    if department_id:
        query = query.filter(Bed.department_id == department_id)

    if patient_id:
        query = query.filter(Patient.id == patient_id)

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(f"%{patient_uid.strip()}%")
        )

    if search:
        term = search.strip()
        filters = [
            Patient.first_name.ilike(f"%{term}%"),
            Patient.last_name.ilike(f"%{term}%"),
            Patient.patient_uid.ilike(f"%{term}%"),
            Patient.phone.ilike(f"%{term}%"),
            Bed.bed_number.ilike(f"%{term}%"),
            Bed.ward_name.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            filters.append(Patient.id == int(term))
        query = query.filter(or_(*filters))

    return query


def _latest_vitals_map(
    db: Session,
    patient_ids: list[int],
) -> dict[int, PatientVitals]:
    if not patient_ids:
        return {}

    latest = (
        db.query(
            PatientVitals.patient_id,
            func.max(PatientVitals.recorded_at).label("latest_at"),
        )
        .filter(PatientVitals.patient_id.in_(patient_ids))
        .group_by(PatientVitals.patient_id)
        .subquery()
    )

    rows = (
        db.query(PatientVitals)
        .join(
            latest,
            and_(
                PatientVitals.patient_id == latest.c.patient_id,
                PatientVitals.recorded_at == latest.c.latest_at,
            ),
        )
        .all()
    )
    return {row.patient_id: row for row in rows}


def _pending_medication_counts(
    db: Session,
    patient_ids: list[int],
) -> dict[int, int]:
    if not patient_ids:
        return {}

    counts = {patient_id: 0 for patient_id in patient_ids}

    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id.in_(patient_ids))
        .order_by(
            Prescription.patient_id.asc(),
            Prescription.created_at.desc(),
        )
        .all()
    )

    latest_rx_by_patient: dict[int, Prescription] = {}
    for prescription in prescriptions:
        if prescription.patient_id not in latest_rx_by_patient:
            latest_rx_by_patient[prescription.patient_id] = prescription

    if not latest_rx_by_patient:
        return counts

    prescription_ids = [
        prescription.id for prescription in latest_rx_by_patient.values()
    ]
    items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id.in_(prescription_ids))
        .all()
    )

    if not items:
        return counts

    item_ids = [item.id for item in items]
    given_rows = (
        db.query(
            MedicationAdministration.prescription_item_id,
            func.count(MedicationAdministration.id),
        )
        .filter(
            MedicationAdministration.prescription_item_id.in_(item_ids),
            MedicationAdministration.status == MedicationStatus.GIVEN,
        )
        .group_by(MedicationAdministration.prescription_item_id)
        .all()
    )
    given_map = {
        prescription_item_id: total
        for prescription_item_id, total in given_rows
    }

    items_by_prescription: dict[int, list[PrescriptionItem]] = defaultdict(list)
    for item in items:
        items_by_prescription[item.prescription_id].append(item)

    for patient_id, prescription in latest_rx_by_patient.items():
        pending = 0
        for item in items_by_prescription.get(prescription.id, []):
            if given_map.get(item.id, 0) == 0:
                pending += 1
        counts[patient_id] = pending

    return counts


def _vital_summary(vital: PatientVitals | None) -> dict | None:
    if not vital:
        return None
    return {
        "vital_id": vital.id,
        "recorded_at": vital.recorded_at,
        "temperature": vital.temperature,
        "blood_pressure": vital.blood_pressure,
        "heart_rate": vital.heart_rate,
        "oxygen_saturation": vital.oxygen_saturation,
        "status": vital.status.value if vital.status else None,
    }


def get_nurse_bed_patients_summary_service(
    db: Session,
    search: str | None = None,
    ward_name: str | None = None,
    bed_number: str | None = None,
    department_id: int | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
):
    query = _base_bed_patients_query(
        db=db,
        search=search,
        ward_name=ward_name,
        bed_number=bed_number,
        department_id=department_id,
        patient_id=patient_id,
        patient_uid=patient_uid,
    )
    return {"success": True, "occupied_count": query.count()}


def get_nurse_bed_patients_service(
    db: Session,
    search: str | None = None,
    ward_name: str | None = None,
    bed_number: str | None = None,
    department_id: int | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = _base_bed_patients_query(
        db=db,
        search=search,
        ward_name=ward_name,
        bed_number=bed_number,
        department_id=department_id,
        patient_id=patient_id,
        patient_uid=patient_uid,
    )

    total = query.count()

    rows = (
        query
        .order_by(Bed.ward_name.asc(), Bed.bed_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    patient_ids = [patient.id for _, patient, _ in rows]
    vitals_map = _latest_vitals_map(db, patient_ids)
    pending_map = _pending_medication_counts(db, patient_ids)

    items = []
    for bed, patient, department in rows:
        items.append({
            "patient_id": patient.id,
            "patient_name": h.display_name(
                patient.first_name,
                patient.last_name,
            ),
            "patient_uid": patient.patient_uid,
            "patient_phone": patient.phone,
            "bed_id": bed.id,
            "bed_number": bed.bed_number,
            "ward_name": bed.ward_name,
            "department_id": bed.department_id,
            "department_name": department.name if department else None,
            "admitted_at": bed.admitted_at,
            "last_vitals": _vital_summary(vitals_map.get(patient.id)),
            "pending_medication_count": pending_map.get(patient.id, 0),
        })

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_nurse_dashboard_stats_service(db: Session) -> dict:
    """Aggregated nurse dashboard counts for today / current ward load."""

    today = date.today()

    queue_rows = (
        db.query(PatientQueue.status, func.count(PatientQueue.id))
        .filter(PatientQueue.queue_date == today)
        .group_by(PatientQueue.status)
        .all()
    )
    queue_by_status: dict[str, int] = {}
    for status, count in queue_rows:
        key = status.value if hasattr(status, "value") else str(status)
        queue_by_status[key] = count

    occupied_beds = (
        db.query(func.count(Bed.id))
        .filter(Bed.status == "occupied", Bed.patient_id.isnot(None))
        .scalar()
        or 0
    )

    active_alerts = (
        db.query(func.count(EmergencyAlert.id))
        .filter(
            EmergencyAlert.status == AlertStatus.ACTIVE,
            EmergencyAlert.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    critical_alerts = (
        db.query(func.count(EmergencyAlert.id))
        .filter(
            EmergencyAlert.status == AlertStatus.ACTIVE,
            EmergencyAlert.is_active.is_(True),
            EmergencyAlert.severity == AlertSeverity.CRITICAL,
        )
        .scalar()
        or 0
    )
    high_alerts = (
        db.query(func.count(EmergencyAlert.id))
        .filter(
            EmergencyAlert.status == AlertStatus.ACTIVE,
            EmergencyAlert.is_active.is_(True),
            EmergencyAlert.severity == AlertSeverity.HIGH,
        )
        .scalar()
        or 0
    )

    submitted_handovers = (
        db.query(func.count(ShiftHandover.id))
        .filter(ShiftHandover.status == HandoverStatus.SUBMITTED)
        .scalar()
        or 0
    )
    awaiting_take_over = (
        db.query(func.count(ShiftHandover.id))
        .filter(
            ShiftHandover.status == HandoverStatus.SUBMITTED,
            ShiftHandover.replacement_nurse_id.is_(None),
        )
        .scalar()
        or 0
    )

    occupied_patient_ids = [
        row[0]
        for row in (
            db.query(Bed.patient_id)
            .filter(Bed.status == "occupied", Bed.patient_id.isnot(None))
            .all()
        )
    ]
    pending_med_map = _pending_medication_counts(db, occupied_patient_ids)
    pending_medications_total = sum(pending_med_map.values())

    return {
        "success": True,
        "queue_today": {
            "total": sum(
                count
                for status, count in queue_by_status.items()
                if status != "no_show"
            ),
            "scheduled": queue_by_status.get("scheduled", 0),
            "completed": queue_by_status.get("completed", 0),
            "cancelled": queue_by_status.get("cancelled", 0),
            "by_status": {
                status: count
                for status, count in queue_by_status.items()
                if status != "no_show"
            },
        },
        "beds": {
            "occupied_count": occupied_beds,
        },
        "alerts": {
            "active_count": active_alerts,
            "critical_count": critical_alerts,
            "high_count": high_alerts,
        },
        "handovers": {
            "submitted_count": submitted_handovers,
            "awaiting_take_over_count": awaiting_take_over,
        },
        "medications": {
            "pending_count_occupied_beds": pending_medications_total,
        },
    }

