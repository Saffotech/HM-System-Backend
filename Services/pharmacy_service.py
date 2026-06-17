from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.doctor_prescriptions import Prescription
from Models.nurse_medication_administration import MedicationAdministration  # noqa: F401 — needed for SQLAlchemy to resolve PrescriptionItem.administrations relationship
from Models.patient import Patient
from Models.pharmacy_dispensing import Dispensing
from Models.user import User
from Schemas.pharmacy_schema import (
    DispenseHistoryItem,
    DispenseRequest,
    PharmacyPrescriptionDetail,
    PharmacyPrescriptionItemOut,
    PharmacyPrescriptionListItem,
)
from Services import opd_helpers as h

PRESCRIPTION_STATUS_PENDING = "pending"
PRESCRIPTION_STATUS_DISPENSED = "dispensed"


def _doctor_name(doctor: Optional[User]) -> str:
    if not doctor:
        return ""
    return h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. ")


def _patient_display_name(rx: Prescription, patient: Optional[Patient]) -> str:
    if rx.patient_name:
        return rx.patient_name
    if patient:
        return h.display_name(patient.first_name, patient.last_name)
    return ""


def list_prescriptions(
    db: Session,
    status: str = PRESCRIPTION_STATUS_PENDING,
    search: Optional[str] = None,
) -> dict:
    q = (
        db.query(Prescription)
        .options(joinedload(Prescription.items))
        .order_by(Prescription.created_at.desc())
    )
    if status:
        q = q.filter(Prescription.status == status)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(Prescription.patient_name.ilike(term))

    rows = q.all()
    doctor_ids = {rx.doctor_id for rx in rows}
    doctors = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    } if doctor_ids else {}

    prescriptions = [
        PharmacyPrescriptionListItem(
            id=rx.id,
            patient_id=rx.patient_id,
            patient_name=rx.patient_name or "",
            doctor_name=_doctor_name(doctors.get(rx.doctor_id)),
            diagnosis=rx.diagnosis,
            medicine_count=len(rx.items),
            status=rx.status or PRESCRIPTION_STATUS_PENDING,
            created_at=rx.created_at,
        )
        for rx in rows
    ]
    return {"total": len(prescriptions), "prescriptions": prescriptions}


def get_prescription_detail(db: Session, prescription_id: int) -> PharmacyPrescriptionDetail:
    rx = (
        db.query(Prescription)
        .options(joinedload(Prescription.items))
        .filter(Prescription.id == prescription_id)
        .first()
    )
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")

    patient = db.query(Patient).filter(Patient.id == rx.patient_id).first()
    doctor = db.query(User).filter(User.id == rx.doctor_id).first()

    return PharmacyPrescriptionDetail(
        id=rx.id,
        patient_id=rx.patient_id,
        patient_name=_patient_display_name(rx, patient),
        patient_phone=patient.phone if patient else None,
        allergies=patient.allergies if patient else None,
        doctor_name=_doctor_name(doctor),
        diagnosis=rx.diagnosis,
        notes=rx.notes,
        status=rx.status or PRESCRIPTION_STATUS_PENDING,
        created_at=rx.created_at,
        items=[PharmacyPrescriptionItemOut.model_validate(i) for i in rx.items],
    )


def dispense_prescription(
    db: Session,
    prescription_id: int,
    data: DispenseRequest,
    pharmacist_id: int,
) -> dict:
    rx = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if rx.status == PRESCRIPTION_STATUS_DISPENSED:
        raise HTTPException(status_code=400, detail="Prescription already dispensed")

    dispensing = Dispensing(
        prescription_id=rx.id,
        dispensed_by=pharmacist_id,
        quantity_dispensed=data.quantity_dispensed,
        remarks=data.remarks,
        batch_number=data.batch_number,
        status=PRESCRIPTION_STATUS_DISPENSED,
    )
    db.add(dispensing)
    rx.status = PRESCRIPTION_STATUS_DISPENSED
    db.commit()
    db.refresh(dispensing)

    return {
        "message": "Medicines dispensed successfully",
        "dispensing_id": dispensing.id,
        "prescription_id": rx.id,
        "status": rx.status,
    }


def get_dispense_history(db: Session, page: int = 1, limit: int = 20) -> dict:
    q = db.query(Dispensing).order_by(Dispensing.dispensed_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * limit).limit(limit).all()

    if not rows:
        return {"total": total, "history": []}

    rx_ids = {d.prescription_id for d in rows}
    pharmacist_ids = {d.dispensed_by for d in rows}

    prescriptions = {
        p.id: p
        for p in db.query(Prescription).filter(Prescription.id.in_(rx_ids)).all()
    }
    pharmacists = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(pharmacist_ids)).all()
    }

    history = [
        DispenseHistoryItem(
            id=d.id,
            prescription_id=d.prescription_id,
            patient_name=prescriptions[d.prescription_id].patient_name or ""
            if d.prescription_id in prescriptions
            else "",
            pharmacist_name=h.display_name(
                pharmacists[d.dispensed_by].first_name,
                pharmacists[d.dispensed_by].last_name,
            )
            if d.dispensed_by in pharmacists
            else "",
            quantity_dispensed=d.quantity_dispensed,
            status=d.status,
            dispensed_at=d.dispensed_at,
        )
        for d in rows
    ]
    return {"total": total, "history": history}
