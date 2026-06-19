from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.patient import Patient
from Models.pharmacy_dispensing import Dispensing, DispensingItem
from Models.user import User
from Schemas.pharmacy_schema import (
    DispenseHistoryItem,
    DispenseItemResponse,
    DispenseRequest,
    PharmacyPrescriptionDetail,
    PharmacyPrescriptionItemOut,
    PharmacyPrescriptionListItem,
)
from Services import opd_helpers as h

PRESCRIPTION_STATUS_PENDING = "pending"
PRESCRIPTION_STATUS_PARTIALLY = "partially_dispensed"
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


def _quantity_prescribed(item: PrescriptionItem) -> int:
    """Use duration as prescribed quantity until a dedicated quantity column exists."""
    return max(int(item.duration or 0), 1)


def _dispensed_totals(db: Session, prescription_item_ids: list[int]) -> dict[int, int]:
    if not prescription_item_ids:
        return {}
    rows = (
        db.query(
            DispensingItem.prescription_item_id,
            func.coalesce(func.sum(DispensingItem.quantity_dispensed), 0),
        )
        .filter(DispensingItem.prescription_item_id.in_(prescription_item_ids))
        .group_by(DispensingItem.prescription_item_id)
        .all()
    )
    return {int(item_id): int(total) for item_id, total in rows}


def _item_out(item: PrescriptionItem, dispensed_so_far: int) -> PharmacyPrescriptionItemOut:
    prescribed = _quantity_prescribed(item)
    remaining = max(prescribed - dispensed_so_far, 0)
    return PharmacyPrescriptionItemOut(
        id=item.id,
        medicine_name=item.medicine_name,
        dosage=item.dosage,
        frequency=item.frequency,
        duration=item.duration,
        instructions=item.instructions,
        quantity_prescribed=prescribed,
        quantity_dispensed=dispensed_so_far,
        quantity_remaining=remaining,
    )


def _compute_prescription_status(
    prescription_items: list[PrescriptionItem],
    dispensed_map: dict[int, int],
) -> str:
    if not prescription_items:
        return PRESCRIPTION_STATUS_PENDING

    complete = 0
    any_dispensed = False
    for item in prescription_items:
        prescribed = _quantity_prescribed(item)
        dispensed = dispensed_map.get(int(item.id), 0)
        if dispensed > 0:
            any_dispensed = True
        if dispensed >= prescribed:
            complete += 1

    if complete == len(prescription_items):
        return PRESCRIPTION_STATUS_DISPENSED
    if any_dispensed:
        return PRESCRIPTION_STATUS_PARTIALLY
    return PRESCRIPTION_STATUS_PENDING


def _patient_uid_map(db: Session, patient_ids: set[int]) -> dict[int, str]:
    if not patient_ids:
        return {}
    rows = (
        db.query(Patient.id, Patient.patient_uid)
        .filter(Patient.id.in_(patient_ids))
        .all()
    )
    return {int(row.id): row.patient_uid for row in rows}


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
    uid_map = _patient_uid_map(db, {int(rx.patient_id) for rx in rows})

    prescriptions = [
        PharmacyPrescriptionListItem(
            id=rx.id,
            patient_id=rx.patient_id,
            patient_uid=uid_map.get(int(rx.patient_id)),
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
    item_ids = [int(i.id) for i in rx.items]
    dispensed_map = _dispensed_totals(db, item_ids)

    return PharmacyPrescriptionDetail(
        id=rx.id,
        patient_id=rx.patient_id,
        patient_uid=patient.patient_uid if patient else None,
        patient_name=_patient_display_name(rx, patient),
        patient_phone=patient.phone if patient else None,
        allergies=patient.allergies if patient else None,
        doctor_name=_doctor_name(doctor),
        diagnosis=rx.diagnosis,
        notes=rx.notes,
        status=rx.status or PRESCRIPTION_STATUS_PENDING,
        created_at=rx.created_at,
        items=[
            _item_out(item, dispensed_map.get(int(item.id), 0))
            for item in rx.items
        ],
    )

def dispense_prescription(
    db: Session,
    prescription_id: int,
    data: DispenseRequest,
    pharmacist_id: int,
) -> dict:
    rx = (
        db.query(Prescription)
        .options(joinedload(Prescription.items))
        .filter(Prescription.id == prescription_id)
        .first()
    )
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if rx.status == PRESCRIPTION_STATUS_DISPENSED:
        raise HTTPException(status_code=400, detail="Prescription already fully dispensed")

    rx_items = {int(item.id): item for item in rx.items}
    if not rx_items:
        raise HTTPException(status_code=400, detail="Prescription has no medicine items")

    seen_item_ids: set[int] = set()
    dispensed_map = _dispensed_totals(db, list(rx_items.keys()))
    response_items: list[DispenseItemResponse] = []
    total_quantity = 0

    for line in data.items:
        item_id = int(line.prescription_item_id)
        if item_id in seen_item_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate prescription_item_id in request: {item_id}",
            )
        seen_item_ids.add(item_id)

        item = rx_items.get(item_id)
        if not item:
            raise HTTPException(
                status_code=400,
                detail=f"prescription_item_id {item_id} does not belong to this prescription",
            )

        prescribed = _quantity_prescribed(item)
        already = dispensed_map.get(item_id, 0)
        remaining = prescribed - already
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Item {item_id} ({item.medicine_name}) is already fully dispensed",
            )
        if line.quantity_dispensed > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"quantity_dispensed exceeds remaining quantity for "
                    f"{item.medicine_name} (remaining: {remaining})"
                ),
            )

        total_quantity += line.quantity_dispensed
        dispensed_map[item_id] = already + line.quantity_dispensed
        response_items.append(
            DispenseItemResponse(
                prescription_item_id=item_id,
                medicine_name=item.medicine_name,
                quantity_dispensed=line.quantity_dispensed,
                quantity_prescribed=prescribed,
                quantity_remaining=max(prescribed - dispensed_map[item_id], 0),
            )
        )

    new_status = _compute_prescription_status(list(rx_items.values()), dispensed_map)
    dispensing = Dispensing(
        prescription_id=rx.id,
        dispensed_by=pharmacist_id,
        quantity_dispensed=total_quantity,
        remarks=data.remarks,
        batch_number=data.batch_number,
        status=new_status,
    )
    db.add(dispensing)
    db.flush()

    for line in data.items:
        db.add(
            DispensingItem(
                dispensing_id=dispensing.id,
                prescription_item_id=int(line.prescription_item_id),
                quantity_dispensed=line.quantity_dispensed,
            )
        )

    rx.status = new_status
    db.commit()
    db.refresh(dispensing)

    return {
        "message": "Medicines dispensed successfully",
        "dispensing_id": dispensing.id,
        "prescription_id": rx.id,
        "status": rx.status,
        "items": response_items,
    }


def get_dispense_history(db: Session, page: int = 1, limit: int = 20) -> dict:
    q = (
        db.query(DispensingItem, Dispensing, PrescriptionItem)
        .join(Dispensing, Dispensing.id == DispensingItem.dispensing_id)
        .join(PrescriptionItem, PrescriptionItem.id == DispensingItem.prescription_item_id)
        .order_by(Dispensing.dispensed_at.desc(), DispensingItem.id.desc())
    )
    total = q.count()
    rows = q.offset((page - 1) * limit).limit(limit).all()

    if not rows:
        return {"total": total, "history": []}

    rx_ids = {d.prescription_id for _, d, _ in rows}
    pharmacist_ids = {d.dispensed_by for _, d, _ in rows}

    prescriptions = {
        p.id: p
        for p in db.query(Prescription).filter(Prescription.id.in_(rx_ids)).all()
    }
    uid_map = _patient_uid_map(
        db,
        {int(p.patient_id) for p in prescriptions.values()},
    )
    pharmacists = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(pharmacist_ids)).all()
    }

    history = [
        DispenseHistoryItem(
            id=line.id,
            dispensing_id=d.id,
            prescription_id=d.prescription_id,
            prescription_item_id=line.prescription_item_id,
            patient_id=prescriptions[d.prescription_id].patient_id
            if d.prescription_id in prescriptions
            else 0,
            patient_uid=uid_map.get(
                int(prescriptions[d.prescription_id].patient_id)
            )
            if d.prescription_id in prescriptions
            else None,
            medicine_name=rx_item.medicine_name,
            patient_name=prescriptions[d.prescription_id].patient_name or ""
            if d.prescription_id in prescriptions
            else "",
            pharmacist_name=h.display_name(
                pharmacists[d.dispensed_by].first_name,
                pharmacists[d.dispensed_by].last_name,
            )
            if d.dispensed_by in pharmacists
            else "",
            quantity_dispensed=line.quantity_dispensed,
            status=d.status,
            dispensed_at=d.dispensed_at,
        )
        for line, d, rx_item in rows
    ]
    return {"total": total, "history": history}
