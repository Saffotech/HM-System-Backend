from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
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
from Services.prescription_duration import duration_to_supply_quantity, normalize_duration

PRESCRIPTION_STATUS_PENDING = "pending"
PRESCRIPTION_STATUS_PARTIALLY = "partially_dispensed"
PRESCRIPTION_STATUS_DISPENSED = "dispensed"

_MONEY_QUANT = Decimal("0.01")


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=h.IST)


def _day_end(day: date) -> datetime:
    return datetime.combine(day, time.max, tzinfo=h.IST)


def _money(value) -> Decimal:
    """Round money to 2 decimal places (HALF_UP)."""
    return Decimal(str(value if value is not None else 0)).quantize(
        _MONEY_QUANT, rounding=ROUND_HALF_UP
    )


def _as_float(value: Decimal) -> float:
    return float(_money(value))


def _unit_price_from_amount(amount: Decimal, quantity: int) -> Decimal:
    if quantity <= 0:
        return _money(0)
    return _money(amount / Decimal(quantity))


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
    """Prefer explicit quantity; old rows fall back to duration-based supply."""
    quantity = getattr(item, "quantity", None)
    if quantity is not None:
        try:
            parsed = int(quantity)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed
    return duration_to_supply_quantity(item.duration)


def _dispensed_aggregates(
    db: Session, prescription_item_ids: list[int]
) -> dict[int, dict[str, Decimal | int]]:
    """
    One query: qty + amount totals per prescription_item_id.
    Returns {item_id: {"qty": int, "amount": Decimal}}.
    """
    if not prescription_item_ids:
        return {}
    rows = (
        db.query(
            DispensingItem.prescription_item_id,
            func.coalesce(func.sum(DispensingItem.quantity_dispensed), 0),
            func.coalesce(func.sum(DispensingItem.amount), 0),
        )
        .filter(DispensingItem.prescription_item_id.in_(prescription_item_ids))
        .group_by(DispensingItem.prescription_item_id)
        .all()
    )
    return {
        int(item_id): {
            "qty": int(qty or 0),
            "amount": _money(amount or 0),
        }
        for item_id, qty, amount in rows
    }


def _item_out(
    item: PrescriptionItem,
    dispensed_qty: int,
    amount_dispensed: Decimal = Decimal("0"),
) -> PharmacyPrescriptionItemOut:
    prescribed = _quantity_prescribed(item)
    remaining = max(prescribed - dispensed_qty, 0)
    unit = (
        _unit_price_from_amount(amount_dispensed, dispensed_qty)
        if dispensed_qty > 0
        else _money(0)
    )
    return PharmacyPrescriptionItemOut(
        id=item.id,
        medicine_name=item.medicine_name,
        dosage=item.dosage,
        frequency=item.frequency,
        duration=normalize_duration(item.duration),
        instructions=item.instructions,
        form=getattr(item, "form", None),
        dose=getattr(item, "dose", None),
        route=getattr(item, "route", None),
        timing=getattr(item, "timing", None),
        quantity=getattr(item, "quantity", None),
        quantity_unit=getattr(item, "quantity_unit", None),
        quantity_prescribed=prescribed,
        quantity_dispensed=dispensed_qty,
        quantity_remaining=remaining,
        unit_price=_as_float(unit),
        amount_dispensed=_as_float(amount_dispensed),
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


def _prescription_item_counts(db: Session, prescription_ids: list[int]) -> dict[int, int]:
    if not prescription_ids:
        return {}
    rows = (
        db.query(PrescriptionItem.prescription_id, func.count(PrescriptionItem.id))
        .filter(PrescriptionItem.prescription_id.in_(prescription_ids))
        .group_by(PrescriptionItem.prescription_id)
        .all()
    )
    return {int(rx_id): int(count) for rx_id, count in rows}


def list_prescriptions(
    db: Session,
    status: str = PRESCRIPTION_STATUS_PENDING,
    search: Optional[str] = None,
) -> dict:
    q = db.query(Prescription).order_by(Prescription.created_at.desc())
    if status:
        q = q.filter(Prescription.status == status)
    if search:
        term = f"%{search.strip()}%"
        q = (
            q.join(Patient, Patient.id == Prescription.patient_id)
            .filter(
                Prescription.patient_name.ilike(term)
                | Patient.patient_uid.ilike(term)
            )
        )

    rows = q.all()
    rx_ids = [rx.id for rx in rows]
    item_counts = _prescription_item_counts(db, rx_ids)
    patient_ids = {rx.patient_id for rx in rows}
    patients = {
        p.id: p
        for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}

    doctor_ids = {rx.doctor_id for rx in rows}
    doctors = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    } if doctor_ids else {}

    prescriptions = [
        PharmacyPrescriptionListItem(
            id=rx.id,
            patient_id=rx.patient_id,
            patient_uid=patients[rx.patient_id].patient_uid
            if rx.patient_id in patients
            else "",
            patient_name=rx.patient_name or "",
            doctor_name=_doctor_name(doctors.get(rx.doctor_id)),
            diagnosis=rx.diagnosis,
            medicine_count=item_counts.get(rx.id, 0),
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

    patient = db.get(Patient, rx.patient_id) if rx.patient_id else None
    doctor = db.get(User, rx.doctor_id) if rx.doctor_id else None
    item_ids = [int(i.id) for i in rx.items]
    aggregates = _dispensed_aggregates(db, item_ids)

    items_out = []
    total_amount = Decimal("0.00")
    for item in rx.items:
        agg = aggregates.get(int(item.id), {"qty": 0, "amount": Decimal("0.00")})
        amount = _money(agg["amount"])
        total_amount += amount
        items_out.append(_item_out(item, int(agg["qty"]), amount))

    return PharmacyPrescriptionDetail(
        id=rx.id,
        patient_id=rx.patient_id,
        patient_uid=patient.patient_uid if patient else "",
        patient_name=_patient_display_name(rx, patient),
        patient_phone=patient.phone if patient else None,
        allergies=patient.allergies if patient else None,
        doctor_name=_doctor_name(doctor),
        diagnosis=rx.diagnosis,
        notes=rx.notes,
        status=rx.status or PRESCRIPTION_STATUS_PENDING,
        created_at=rx.created_at,
        total_amount_dispensed=_as_float(total_amount),
        items=items_out,
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
    aggregates = _dispensed_aggregates(db, list(rx_items.keys()))
    dispensed_map = {item_id: int(agg["qty"]) for item_id, agg in aggregates.items()}

    prepared_lines: list[dict] = []
    response_items: list[DispenseItemResponse] = []
    total_quantity = 0
    total_amount = Decimal("0.00")

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

        qty = int(line.quantity_dispensed)
        amount = _money(line.amount)
        unit_price = _unit_price_from_amount(amount, qty)

        prescribed = _quantity_prescribed(item)
        already = dispensed_map.get(item_id, 0)
        remaining = prescribed - already
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Item {item_id} ({item.medicine_name}) is already fully dispensed",
            )
        if qty > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"quantity_dispensed exceeds remaining quantity for "
                    f"{item.medicine_name} (remaining: {remaining})"
                ),
            )

        total_quantity += qty
        total_amount += amount
        next_dispensed = already + qty
        dispensed_map[item_id] = next_dispensed

        prepared_lines.append(
            {
                "item": item,
                "item_id": item_id,
                "qty": qty,
                "amount": amount,
                "unit_price": unit_price,
            }
        )
        response_items.append(
            DispenseItemResponse(
                prescription_item_id=item_id,
                medicine_name=item.medicine_name,
                quantity_dispensed=qty,
                quantity_prescribed=prescribed,
                quantity_remaining=max(prescribed - next_dispensed, 0),
                unit_price=_as_float(unit_price),
                amount=_as_float(amount),
            )
        )

    new_status = _compute_prescription_status(list(rx_items.values()), dispensed_map)
    dispensing = Dispensing(
        prescription_id=rx.id,
        dispensed_by=pharmacist_id,
        quantity_dispensed=total_quantity,
        total_amount=total_amount,
        remarks=data.remarks,
        batch_number=data.batch_number,
        status=new_status,
    )
    db.add(dispensing)
    db.flush()

    db.add_all(
        [
            DispensingItem(
                dispensing_id=dispensing.id,
                prescription_item_id=row["item_id"],
                medicine_name=row["item"].medicine_name,
                quantity_dispensed=row["qty"],
                unit_price=row["unit_price"],
                amount=row["amount"],
            )
            for row in prepared_lines
        ]
    )

    rx.status = new_status
    db.commit()
    db.refresh(dispensing)

    return {
        "message": "Medicines dispensed successfully",
        "dispensing_id": dispensing.id,
        "prescription_id": rx.id,
        "status": rx.status,
        "total_amount": _as_float(total_amount),
        "items": response_items,
    }


def get_dispense_history(
    db: Session,
    page: int = 1,
    limit: int = 20,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    prescription_id: Optional[int] = None,
) -> dict:
    q = (
        db.query(DispensingItem, Dispensing, PrescriptionItem)
        .join(Dispensing, Dispensing.id == DispensingItem.dispensing_id)
        .join(PrescriptionItem, PrescriptionItem.id == DispensingItem.prescription_item_id)
        .order_by(Dispensing.dispensed_at.desc(), DispensingItem.id.desc())
    )
    if prescription_id is not None:
        q = q.filter(Dispensing.prescription_id == prescription_id)
    if date_from is not None:
        q = q.filter(Dispensing.dispensed_at >= _day_start(date_from))
    if date_to is not None:
        q = q.filter(Dispensing.dispensed_at <= _day_end(date_to))

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
    pharmacists = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(pharmacist_ids)).all()
    }
    patient_ids = {p.patient_id for p in prescriptions.values()}
    patients = {
        p.id: p
        for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}

    history = [
        DispenseHistoryItem(
            id=line.id,
            dispensing_id=d.id,
            patient_uid=patients[prescriptions[d.prescription_id].patient_id].patient_uid
            if d.prescription_id in prescriptions
            and prescriptions[d.prescription_id].patient_id in patients
            else None,
            prescription_id=d.prescription_id,
            prescription_item_id=line.prescription_item_id,
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
            unit_price=_as_float(getattr(line, "unit_price", 0) or 0),
            amount=_as_float(getattr(line, "amount", 0) or 0),
            status=d.status,
            dispensed_at=d.dispensed_at,
        )
        for line, d, rx_item in rows
    ]
    return {"total": total, "history": history}
