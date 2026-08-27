"""Unified IPD admission billing — auto bed/visit/pharmacy + saved daily/final charges."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_prescriptions import Prescription
from Models.ipd import (
    IpdAdmission,
    IpdAdmissionBilling,
    IpdDoctorVisit,
    IpdInsuranceClaim,
)
from Models.pharmacy_dispensing import Dispensing, DispensingItem
from Services import ipd_helpers as h
from Services import ipd_insurance_service as ins
from Services import opd_settings_service

IST = ZoneInfo("Asia/Kolkata")

DEFAULT_CHARGE_HEADS: list[dict[str, Any]] = [
    {
        "id": "room",
        "charge_category": "room",
        "label": "Room Charges",
        "amount": 0,
        "is_default": True,
        "sort_order": 1,
    },
    {
        "id": "doctor",
        "charge_category": "doctor",
        "label": "Doctor Charges",
        "amount": 0,
        "is_default": True,
        "sort_order": 2,
    },
    {
        "id": "lab",
        "charge_category": "laboratory",
        "label": "Laboratory",
        "amount": 0,
        "is_default": True,
        "sort_order": 3,
    },
    {
        "id": "pharmacy",
        "charge_category": "pharmacy",
        "label": "Pharmacy",
        "amount": 0,
        "is_default": True,
        "sort_order": 4,
    },
    {
        "id": "procedure",
        "charge_category": "procedure",
        "label": "Treatment",
        "amount": 0,
        "is_default": True,
        "sort_order": 5,
    },
    {
        "id": "misc",
        "charge_category": "miscellaneous",
        "label": "Miscellaneous",
        "amount": 0,
        "is_default": True,
        "sort_order": 6,
    },
    {
        "id": "discount",
        "charge_category": "discount",
        "label": "Discount",
        "amount": 0,
        "is_default": True,
        "sort_order": 99,
    },
]

CATEGORY_TO_HEAD = {
    "room": ("room", "Room Charges"),
    "doctor": ("doctor", "Doctor Charges"),
    "laboratory": ("lab", "Laboratory"),
    "pharmacy": ("pharmacy", "Pharmacy"),
    "procedure": ("procedure", "Treatment"),
    "miscellaneous": ("misc", "Miscellaneous"),
    "discount": ("discount", "Discount"),
    "custom": ("misc", "Miscellaneous"),
}


def _now() -> datetime:
    return datetime.now(IST)


def _iso_date(value: datetime | date | None) -> str:
    if value is None:
        return datetime.now(IST).date().isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=IST)
        return value.astimezone(IST).date().isoformat()
    return value.isoformat()


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _clone_default_heads() -> list[dict[str, Any]]:
    return [dict(row) for row in DEFAULT_CHARGE_HEADS]


def _get_or_create_billing(db: Session, admission_id: int) -> IpdAdmissionBilling:
    row = (
        db.query(IpdAdmissionBilling)
        .filter(IpdAdmissionBilling.admission_id == admission_id)
        .first()
    )
    if row:
        return row
    row = IpdAdmissionBilling(
        admission_id=admission_id,
        charge_heads=[],
        daily_charges=[],
    )
    db.add(row)
    db.flush()
    return row


def _stay_dates(admitted_at: datetime | None, days: int) -> list[str]:
    days = max(1, int(days or 1))
    if not admitted_at:
        end = datetime.now(IST).date()
        start = end - timedelta(days=days - 1)
    else:
        start = (
            admitted_at.replace(tzinfo=IST)
            if admitted_at.tzinfo is None
            else admitted_at.astimezone(IST)
        ).date()
        end = start + timedelta(days=days - 1)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _tx(
    *,
    tx_id: str,
    admission_id: int,
    patient_id: int,
    charge_date: str,
    category: str,
    particulars: str,
    quantity: float,
    rate: float,
    amount: float,
    source: str,
    source_id: Any = None,
) -> dict[str, Any]:
    head_id, head_label = CATEGORY_TO_HEAD.get(category, ("misc", "Miscellaneous"))
    return {
        "id": tx_id,
        "admission_id": admission_id,
        "admissionId": str(admission_id),
        "patient_id": patient_id,
        "patientId": str(patient_id),
        "charge_date": charge_date,
        "chargeDate": charge_date,
        "category": category,
        "charge_category": category,
        "particulars": particulars,
        "item_name": particulars,
        "quantity": quantity,
        "rate": rate,
        "unit_price": rate,
        "amount": amount,
        "source": source,
        "source_id": source_id,
        "sourceId": source_id,
        "head": head_label,
        "status": "active",
        "is_auto": source != "manual",
        "isAuto": source != "manual",
    }


def build_auto_transactions(db: Session, admission: IpdAdmission) -> list[dict[str, Any]]:
    """Bed (per day) + doctor visits + pharmacy dispensings for this admission."""
    pricing = opd_settings_service.get_pricing(db)
    days = opd_settings_service.calculate_bed_days(admission.admitted_at)
    rate = _money(
        opd_settings_service.resolve_bed_rate(
            pricing,
            bed_number=admission.bed_number,
            ward_name=admission.ward_name,
        )
    )
    bed_label = f"Bed Charge ({admission.bed_number or admission.ward_name or 'Bed'})"
    txs: list[dict[str, Any]] = []

    for charge_date in _stay_dates(admission.admitted_at, days):
        if rate <= 0:
            continue
        txs.append(
            _tx(
                tx_id=f"auto-bed-{admission.id}-{charge_date}",
                admission_id=admission.id,
                patient_id=admission.patient_id,
                charge_date=charge_date,
                category="room",
                particulars=bed_label,
                quantity=1,
                rate=rate,
                amount=rate,
                source="room",
                source_id=admission.bed_id,
            )
        )

    visits = (
        db.query(IpdDoctorVisit)
        .filter(
            IpdDoctorVisit.admission_id == admission.id,
            IpdDoctorVisit.is_voided.is_(False),
        )
        .order_by(IpdDoctorVisit.visited_at.asc(), IpdDoctorVisit.id.asc())
        .all()
    )
    for visit in visits:
        amount = _money(visit.charge)
        if amount <= 0:
            continue
        doc = h.doctor_display(db, visit.doctor_id) or "Doctor"
        txs.append(
            _tx(
                tx_id=f"auto-visit-{visit.id}",
                admission_id=admission.id,
                patient_id=admission.patient_id,
                charge_date=_iso_date(visit.visited_at),
                category="doctor",
                particulars=f"Doctor Visit — {doc}",
                quantity=1,
                rate=amount,
                amount=amount,
                source="doctor",
                source_id=visit.id,
            )
        )

    # Pharmacy: dispensings for prescriptions linked to this admission
    dispense_rows = (
        db.query(DispensingItem, Dispensing)
        .join(Dispensing, Dispensing.id == DispensingItem.dispensing_id)
        .join(Prescription, Prescription.id == Dispensing.prescription_id)
        .filter(Prescription.admission_id == admission.id)
        .order_by(Dispensing.dispensed_at.asc(), DispensingItem.id.asc())
        .all()
    )
    for item, dispensing in dispense_rows:
        amount = _money(item.amount)
        if amount <= 0:
            continue
        qty = max(int(item.quantity_dispensed or 1), 1)
        rate = _money(item.unit_price) if item.unit_price is not None else (
            round(amount / qty, 2) if qty else amount
        )
        txs.append(
            _tx(
                tx_id=f"auto-pharmacy-{item.id}",
                admission_id=admission.id,
                patient_id=admission.patient_id,
                charge_date=_iso_date(dispensing.dispensed_at),
                category="pharmacy",
                particulars=item.medicine_name or "Pharmacy item",
                quantity=qty,
                rate=rate,
                amount=amount,
                source="pharmacy",
                source_id=item.id,
            )
        )

    return txs


def _is_manual_row(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "").strip().lower()
    row_id = str(row.get("id") or "")
    if row.get("is_auto") is True or row.get("isAuto") is True:
        return False
    if row_id.startswith("auto-"):
        return False
    if source and source != "manual":
        return False
    return True


def _normalize_daily_row(row: dict[str, Any], admission: IpdAdmission) -> dict[str, Any]:
    category = str(
        row.get("charge_category")
        or row.get("category")
        or "miscellaneous"
    ).strip().lower()
    head = str(row.get("head") or "").strip()
    if not head:
        _, head = CATEGORY_TO_HEAD.get(category, ("misc", "Miscellaneous"))
    amount = _money(row.get("amount"))
    qty_raw = row.get("quantity")
    try:
        quantity = float(qty_raw)
    except (TypeError, ValueError):
        quantity = 1.0
    if quantity <= 0:
        quantity = 1.0
    rate = _money(row.get("rate") or row.get("unit_price"))
    if rate <= 0 and quantity:
        rate = round(amount / quantity, 2)
    charge_date = str(row.get("charge_date") or row.get("chargeDate") or "")[:10]
    if not charge_date:
        charge_date = _iso_date(_now())
    particulars = str(
        row.get("item_name")
        or row.get("particulars")
        or row.get("description")
        or head
    ).strip()
    source = str(row.get("source") or "manual").strip().lower() or "manual"
    row_id = str(row.get("id") or f"manual-{admission.id}-{charge_date}-{particulars}")
    return _tx(
        tx_id=row_id,
        admission_id=admission.id,
        patient_id=admission.patient_id,
        charge_date=charge_date,
        category=category,
        particulars=particulars,
        quantity=quantity,
        rate=rate,
        amount=amount,
        source=source if source != "manual" else "manual",
        source_id=row.get("source_id") or row.get("sourceId"),
    )


def merge_daily_transactions(
    auto_txs: list[dict[str, Any]],
    stored_daily: list[Any],
    admission: IpdAdmission,
) -> list[dict[str, Any]]:
    manual = [
        _normalize_daily_row(row, admission)
        for row in (stored_daily or [])
        if isinstance(row, dict) and _is_manual_row(row)
    ]
    if not manual:
        return auto_txs

    manual_room_dates = {
        row["charge_date"]
        for row in manual
        if row.get("category") == "room"
    }
    auto_kept = [
        row
        for row in auto_txs
        if not (
            row.get("category") == "room"
            and row.get("charge_date") in manual_room_dates
        )
    ]
    return sorted(
        auto_kept + manual,
        key=lambda r: (r.get("charge_date") or "", r.get("id") or ""),
    )


def transactions_to_daily_charges(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for tx in transactions:
        rows.append(
            {
                "id": tx["id"],
                "charge_date": tx["charge_date"],
                "head": tx.get("head"),
                "charge_category": tx.get("category"),
                "item_name": tx.get("particulars"),
                "quantity": tx.get("quantity"),
                "amount": tx.get("amount"),
                "source": tx.get("source"),
                "source_id": tx.get("source_id"),
                "is_auto": tx.get("source") != "manual",
                "isAuto": tx.get("source") != "manual",
            }
        )
    return rows


def rollup_charge_heads(
    transactions: list[dict[str, Any]],
    stored_heads: Optional[list[Any]] = None,
) -> list[dict[str, Any]]:
    heads = _clone_default_heads()
    stored_map: dict[str, dict[str, Any]] = {}
    for row in stored_heads or []:
        if not isinstance(row, dict):
            continue
        hid = str(row.get("id") or "")
        if hid:
            stored_map[hid] = row

    sums: dict[str, float] = {
        "room": 0.0,
        "doctor": 0.0,
        "laboratory": 0.0,
        "pharmacy": 0.0,
        "procedure": 0.0,
        "miscellaneous": 0.0,
    }
    for tx in transactions:
        cat = str(tx.get("category") or "miscellaneous")
        if cat in sums:
            sums[cat] = round(sums[cat] + _money(tx.get("amount")), 2)

    out: list[dict[str, Any]] = []
    for head in heads:
        hid = head["id"]
        stored = stored_map.get(hid)
        category = head["charge_category"]
        rolled = sums.get(category, 0.0)
        if category == "discount":
            amount = _money(stored.get("amount")) if stored else 0.0
        else:
            # Prefer rolled auto+manual totals; keep stored override if rolled is 0
            # but stored has a positive amount (manual final edit without dailies).
            stored_amt = _money(stored.get("amount")) if stored else 0.0
            amount = rolled if rolled > 0 else stored_amt
        out.append(
            {
                **head,
                "label": (stored or {}).get("label") or head["label"],
                "amount": amount,
                "is_default": True,
                "sort_order": head["sort_order"],
            }
        )

    # Preserve custom heads from stored
    for hid, stored in stored_map.items():
        if any(h["id"] == hid for h in out):
            continue
        out.append(
            {
                "id": hid,
                "charge_category": stored.get("charge_category") or "custom",
                "label": stored.get("label") or "Charge",
                "amount": _money(stored.get("amount")),
                "is_default": False,
                "sort_order": stored.get("sort_order") or 50,
            }
        )

    out.sort(key=lambda r: int(r.get("sort_order") or 0))
    return out


def _normalize_charge_heads(rows: list[Any]) -> list[dict[str, Any]]:
    if not rows:
        return _clone_default_heads()
    out = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        hid = str(row.get("id") or f"custom-{index}")
        template = next((t for t in DEFAULT_CHARGE_HEADS if t["id"] == hid), None)
        out.append(
            {
                "id": hid,
                "charge_category": row.get("charge_category")
                or (template["charge_category"] if template else "custom"),
                "label": row.get("label")
                or (template["label"] if template else "Charge"),
                "amount": _money(row.get("amount")),
                "is_default": bool(
                    row.get("is_default")
                    if row.get("is_default") is not None
                    else bool(template)
                ),
                "sort_order": int(
                    row.get("sort_order")
                    or (template["sort_order"] if template else 50 + index)
                ),
            }
        )
    out.sort(key=lambda r: int(r.get("sort_order") or 0))
    return out


def get_billing_bundle(db: Session, admission_id: int) -> dict[str, Any]:
    admission = h.get_admission(db, admission_id)
    billing = (
        db.query(IpdAdmissionBilling)
        .filter(IpdAdmissionBilling.admission_id == admission.id)
        .first()
    )
    stored_daily = list(billing.daily_charges or []) if billing else []
    stored_heads = list(billing.charge_heads or []) if billing else []

    auto_txs = build_auto_transactions(db, admission)
    transactions = merge_daily_transactions(auto_txs, stored_daily, admission)
    charge_heads = rollup_charge_heads(transactions, stored_heads)
    daily_charges = transactions_to_daily_charges(transactions)

    claim_row = (
        db.query(IpdInsuranceClaim)
        .filter(IpdInsuranceClaim.admission_id == admission.id)
        .first()
    )
    claim_out = None
    patient_out = None
    if claim_row:
        bundle = ins.serialize_patient_bundle(db, claim_row)
        claim_out = bundle["claim"]
        patient_out = bundle["patient"]
        # Attach live billing onto claim for FE claim.charges / dailyCharges
        claim_out["charges"] = charge_heads
        claim_out["daily_charges"] = daily_charges
        claim_out["dailyCharges"] = daily_charges
        net = sum(
            _money(h.get("amount"))
            for h in charge_heads
            if h.get("charge_category") != "discount"
        ) - sum(
            _money(h.get("amount"))
            for h in charge_heads
            if h.get("charge_category") == "discount"
        )
        claim_out["net_bill"] = round(net, 2)
        claim_out["netBill"] = round(net, 2)

    preview = None
    try:
        from Services import ipd_service

        preview = ipd_service.build_bill_preview(db, admission.id).model_dump()
    except Exception:
        preview = None

    return {
        "admission_id": admission.id,
        "admissionId": admission.id,
        "patient_id": admission.patient_id,
        "patientId": admission.patient_id,
        "claim_id": claim_row.id if claim_row else None,
        "claimId": claim_row.id if claim_row else None,
        "payment_type": getattr(admission, "payment_type", None) or "self",
        "patient": patient_out,
        "claim": claim_out,
        "transactions": transactions,
        "daily_charges": daily_charges,
        "dailyCharges": daily_charges,
        "charge_heads": charge_heads,
        "chargeHeads": charge_heads,
        "preview": preview,
    }


def update_daily_billing(
    db: Session,
    admission_id: int,
    payload: dict[str, Any],
    *,
    updated_by: Optional[int] = None,
) -> dict[str, Any]:
    admission = h.get_admission(db, admission_id)
    raw_daily = (
        payload.get("dailyCharges")
        if payload.get("dailyCharges") is not None
        else payload.get("daily_charges")
    )
    if raw_daily is None:
        raise HTTPException(status_code=400, detail="dailyCharges is required")
    if not isinstance(raw_daily, list):
        raise HTTPException(status_code=400, detail="dailyCharges must be a list")

    # Persist only manual rows; auto lines always regenerated on read
    manual_only = [
        _normalize_daily_row(row, admission)
        for row in raw_daily
        if isinstance(row, dict) and _is_manual_row(row)
    ]
    # Store UI-friendly daily shape
    stored = transactions_to_daily_charges(manual_only)

    billing = _get_or_create_billing(db, admission.id)
    billing.daily_charges = stored
    billing.updated_by = updated_by
    billing.updated_at = _now()

    # Keep rolled charge heads in sync unless client also sent heads
    auto_txs = build_auto_transactions(db, admission)
    merged = merge_daily_transactions(auto_txs, stored, admission)
    if payload.get("charges") is not None or payload.get("charge_heads") is not None:
        heads_in = payload.get("charges") or payload.get("charge_heads") or []
        billing.charge_heads = _normalize_charge_heads(heads_in)
    else:
        billing.charge_heads = rollup_charge_heads(merged, billing.charge_heads or [])

    db.commit()
    return get_billing_bundle(db, admission.id)


def update_final_billing(
    db: Session,
    admission_id: int,
    payload: dict[str, Any],
    *,
    updated_by: Optional[int] = None,
) -> dict[str, Any]:
    admission = h.get_admission(db, admission_id)
    heads_in = (
        payload.get("charges")
        if payload.get("charges") is not None
        else payload.get("charge_heads")
    )
    if heads_in is None:
        raise HTTPException(status_code=400, detail="charges is required")
    if not isinstance(heads_in, list):
        raise HTTPException(status_code=400, detail="charges must be a list")

    billing = _get_or_create_billing(db, admission.id)
    billing.charge_heads = _normalize_charge_heads(heads_in)
    billing.updated_by = updated_by
    billing.updated_at = _now()

    if payload.get("dailyCharges") is not None or payload.get("daily_charges") is not None:
        raw_daily = payload.get("dailyCharges")
        if raw_daily is None:
            raw_daily = payload.get("daily_charges")
        if isinstance(raw_daily, list):
            manual_only = [
                _normalize_daily_row(row, admission)
                for row in raw_daily
                if isinstance(row, dict) and _is_manual_row(row)
            ]
            billing.daily_charges = transactions_to_daily_charges(manual_only)

    db.commit()
    return get_billing_bundle(db, admission.id)


def get_daily_billing(db: Session, admission_id: int) -> dict[str, Any]:
    bundle = get_billing_bundle(db, admission_id)
    return {
        "admission_id": bundle["admission_id"],
        "daily_charges": bundle["daily_charges"],
        "transactions": bundle["transactions"],
    }


def get_final_billing(db: Session, admission_id: int) -> dict[str, Any]:
    bundle = get_billing_bundle(db, admission_id)
    return {
        "admission_id": bundle["admission_id"],
        "charge_heads": bundle["charge_heads"],
        "charges": bundle["charge_heads"],
    }
