"""IPD admissions, beds, visits, billing, discharge, and dashboard."""
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.department import Department
from Models.ipd import (
    IpdAdmission,
    IpdBill,
    IpdBillItem,
    IpdDoctorVisit,
    IpdPaymentTransaction,
)
from Models.patient import Patient
from Models.user import User
from Schemas.ipd_schema import (
    IpdAdmitRequest,
    IpdAdmissionOut,
    IpdAdmissionUpdate,
    IpdBillItemOut,
    IpdBillOut,
    IpdBillPreviewOut,
    IpdCollectPaymentRequest,
    IpdDischargeRequest,
    IpdDoctorVisitCreate,
    IpdDoctorVisitOut,
    IpdGenerateBillRequest,
    IpdTransferBedRequest,
)
from Services import bed_service
from Services import ipd_helpers as h
from Services import opd_helpers as oh
from Services import opd_settings_service


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return h.now_ist()
    try:
        raw = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo

            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return dt
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime format") from exc


def _admission_doctor_name(db: Session, row: IpdAdmission) -> Optional[str]:
    if row.doctor_id:
        return h.doctor_display(db, row.doctor_id)
    visit = (
        db.query(IpdDoctorVisit)
        .filter(IpdDoctorVisit.admission_id == row.id)
        .order_by(IpdDoctorVisit.visited_at.desc())
        .first()
    )
    if visit:
        return h.doctor_display(db, visit.doctor_id)
    return None


def _admission_out(db: Session, row: IpdAdmission) -> IpdAdmissionOut:
    patient = db.query(Patient).filter(Patient.id == row.patient_id).first()
    dept = (
        db.query(Department).filter(Department.id == row.department_id).first()
        if row.department_id
        else None
    )
    days = opd_settings_service.calculate_bed_days(row.admitted_at)
    return IpdAdmissionOut(
        id=row.id,
        admission_no=row.admission_no,
        patient_id=row.patient_id,
        patient_uid=patient.patient_uid if patient else None,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else None,
        bed_id=row.bed_id,
        bed_number=row.bed_number,
        ward_name=row.ward_name,
        doctor_id=row.doctor_id,
        doctor_name=_admission_doctor_name(db, row),
        department_id=row.department_id,
        department_name=dept.name if dept else None,
        diagnosis=row.diagnosis,
        notes=row.notes,
        status=row.status,
        admitted_at=_iso(row.admitted_at),
        discharged_at=_iso(row.discharged_at),
        length_of_stay_days=days,
    )


def admit_patient(db: Session, data: IpdAdmitRequest, admitted_by: int) -> IpdAdmissionOut:
    patient = h.get_patient(db, data.patient_id)
    existing = h.get_active_admission_for_patient(db, patient.id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Patient already has an active IPD admission ({existing.admission_no})",
        )

    bed = h.get_bed(db, data.bed_id)
    if data.doctor_id and data.department_id:
        oh.get_doctor_in_department(db, data.doctor_id, data.department_id)
    elif data.department_id:
        oh.get_department(db, data.department_id)

    h.occupy_bed(db, bed, patient.id, data.department_id)

    admission = IpdAdmission(
        admission_no=h.next_admission_no(db),
        patient_id=patient.id,
        bed_id=bed.id,
        doctor_id=data.doctor_id,
        department_id=data.department_id,
        ward_name=bed.ward_name,
        bed_number=bed.bed_number,
        diagnosis=data.diagnosis,
        notes=data.notes,
        status="admitted",
        admitted_at=_parse_dt(data.admission_date),
        admitted_by=admitted_by,
    )
    # Align bed.admitted_at with admission start for tariff day calc consistency
    bed.admitted_at = admission.admitted_at

    db.add(admission)
    db.commit()
    db.refresh(admission)
    return _admission_out(db, admission)


def update_admission(
    db: Session,
    admission_id: int,
    data: IpdAdmissionUpdate,
) -> IpdAdmissionOut:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Only active admissions can be updated")

    updates = data.model_dump(exclude_unset=True)
    next_department_id = updates.get("department_id", admission.department_id)

    if "department_id" in updates:
        admission.department_id = updates["department_id"]
    if "doctor_id" in updates:
        doctor_id = updates["doctor_id"]
        if doctor_id is not None and next_department_id:
            oh.get_doctor_in_department(db, doctor_id, next_department_id)
        admission.doctor_id = doctor_id
    if "diagnosis" in updates:
        admission.diagnosis = updates["diagnosis"]
    if "notes" in updates:
        admission.notes = updates["notes"]

    db.commit()
    db.refresh(admission)
    return _admission_out(db, admission)


def transfer_bed(
    db: Session, data: IpdTransferBedRequest, transferred_by: Optional[int] = None
) -> IpdAdmissionOut:
    if data.admission_id:
        admission = h.get_admission(db, data.admission_id)
    else:
        from_bed = h.get_bed(db, data.from_bed_id)
        admission = h.ensure_admission_for_occupied_bed(
            db, from_bed, admitted_by=transferred_by
        )

    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Only active admissions can transfer beds")

    if admission.bed_id == data.new_bed_id:
        raise HTTPException(status_code=400, detail="Patient is already on this bed")

    new_bed = h.get_bed(db, data.new_bed_id)
    old_bed = h.get_bed(db, admission.bed_id) if admission.bed_id else None

    h.occupy_bed(db, new_bed, admission.patient_id, admission.department_id)
    # Keep stay start for billing; occupancy timestamp on new bed is now
    new_bed.admitted_at = admission.admitted_at
    h.free_bed(db, old_bed)

    admission.bed_id = new_bed.id
    admission.ward_name = new_bed.ward_name
    admission.bed_number = new_bed.bed_number

    db.commit()
    db.refresh(admission)
    return _admission_out(db, admission)


def list_admissions(
    db: Session,
    *,
    status: Optional[str] = None,
    ward: Optional[str] = None,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    admission_date: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    page = max(1, page)
    limit = min(max(1, limit), 100)

    q = db.query(IpdAdmission)
    if status:
        q = q.filter(IpdAdmission.status == status.lower())
    if ward:
        q = q.filter(IpdAdmission.ward_name == ward)
    if doctor_id:
        q = q.filter(IpdAdmission.doctor_id == doctor_id)
    if admission_date:
        try:
            day = datetime.strptime(admission_date[:10], "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid admission_date") from exc
        from sqlalchemy import cast, Date

        q = q.filter(cast(IpdAdmission.admitted_at, Date) == day)

    if search:
        term = f"%{search.strip()}%"
        q = (
            q.join(Patient, IpdAdmission.patient_id == Patient.id)
            .filter(
                (Patient.first_name.ilike(term))
                | (Patient.last_name.ilike(term))
                | (Patient.phone.ilike(term))
                | (Patient.patient_uid.ilike(term))
                | (IpdAdmission.admission_no.ilike(term))
                | (IpdAdmission.bed_number.ilike(term))
            )
        )

    total = q.count()
    rows = (
        q.order_by(IpdAdmission.admitted_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [_admission_out(db, r) for r in rows],
    }


def get_admission_detail(db: Session, admission_id: int) -> dict:
    admission = h.get_admission(db, admission_id)
    visits = (
        db.query(IpdDoctorVisit)
        .filter(IpdDoctorVisit.admission_id == admission.id)
        .order_by(IpdDoctorVisit.visited_at.desc())
        .all()
    )
    bills = (
        db.query(IpdBill)
        .filter(IpdBill.admission_id == admission.id)
        .order_by(IpdBill.generated_at.desc())
        .all()
    )
    preview = build_bill_preview(db, admission.id)
    return {
        "admission": _admission_out(db, admission),
        "doctor_visits": [_visit_out(db, v) for v in visits],
        "bills": [_bill_out(db, b) for b in bills],
        "running_bill": preview.model_dump(),
    }


def _visit_out(db: Session, visit: IpdDoctorVisit) -> IpdDoctorVisitOut:
    return IpdDoctorVisitOut(
        id=visit.id,
        admission_id=visit.admission_id,
        doctor_id=visit.doctor_id,
        doctor_name=h.doctor_display(db, visit.doctor_id),
        visited_at=_iso(visit.visited_at),
        charge=float(visit.charge or 0),
        notes=visit.notes,
    )


def add_doctor_visit(
    db: Session, admission_id: int, data: IpdDoctorVisitCreate, recorded_by: int
) -> IpdDoctorVisitOut:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Cannot add visits to a closed admission")

    doctor = db.query(User).filter(User.id == data.doctor_id, User.is_active.is_(True)).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    pricing = opd_settings_service.get_pricing(db)
    if data.charge is not None:
        charge = float(data.charge)
    else:
        charge = float(
            opd_settings_service.resolve_consultation_fee(
                pricing,
                doctor_id=data.doctor_id,
                department_id=admission.department_id or doctor.department_id,
            )
        )

    visit = IpdDoctorVisit(
        admission_id=admission.id,
        doctor_id=data.doctor_id,
        visited_at=_parse_dt(data.visited_at),
        charge=charge,
        notes=data.notes,
        recorded_by=recorded_by,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return _visit_out(db, visit)


def _charge_lines_for_admission(db: Session, admission: IpdAdmission) -> tuple[list[dict], float, int]:
    pricing = opd_settings_service.get_pricing(db)
    days = opd_settings_service.calculate_bed_days(admission.admitted_at)
    rate = float(
        opd_settings_service.resolve_bed_rate(
            pricing,
            bed_number=admission.bed_number,
            ward_name=admission.ward_name,
        )
    )
    items: list[dict] = [
        {
            "description": f"Bed Charge ({admission.bed_number or admission.ward_name or 'Bed'})",
            "qty": days,
            "unit_price": rate,
            "amount": round(days * rate, 2),
            "item_type": "bed",
        }
    ]

    visits = (
        db.query(IpdDoctorVisit)
        .filter(IpdDoctorVisit.admission_id == admission.id)
        .order_by(IpdDoctorVisit.visited_at.asc())
        .all()
    )
    for v in visits:
        doc = h.doctor_display(db, v.doctor_id) or "Doctor"
        items.append(
            {
                "description": f"Doctor Visit — {doc}",
                "qty": 1,
                "unit_price": float(v.charge or 0),
                "amount": round(float(v.charge or 0), 2),
                "item_type": "visit",
            }
        )

    subtotal = round(sum(i["amount"] for i in items), 2)
    return items, subtotal, days


def build_bill_preview(db: Session, admission_id: int) -> IpdBillPreviewOut:
    admission = h.get_admission(db, admission_id)
    items, subtotal, days = _charge_lines_for_admission(db, admission)
    pricing = opd_settings_service.get_pricing(db)
    gst_percent = float(getattr(pricing, "gst_percent", None) or 0)
    _, gst_amount, grand = oh.bill_totals_from_subtotal(subtotal, gst_percent)
    patient = db.query(Patient).filter(Patient.id == admission.patient_id).first()
    rate = float(
        opd_settings_service.resolve_bed_rate(
            pricing,
            bed_number=admission.bed_number,
            ward_name=admission.ward_name,
        )
    )
    return IpdBillPreviewOut(
        admission_id=admission.id,
        admission_no=admission.admission_no,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else None,
        ward_name=admission.ward_name,
        bed_number=admission.bed_number,
        length_of_stay_days=days,
        bed_rate=rate,
        items=[IpdBillItemOut(**i) for i in items],
        subtotal=subtotal,
        gst_percent=gst_percent,
        gst_amount=gst_amount,
        grand_total=grand,
    )


def _bill_out(db: Session, bill: IpdBill) -> IpdBillOut:
    items = (
        db.query(IpdBillItem)
        .filter(IpdBillItem.bill_id == bill.id)
        .order_by(IpdBillItem.id.asc())
        .all()
    )
    return IpdBillOut(
        id=bill.id,
        bill_number=bill.bill_number,
        admission_id=bill.admission_id,
        subtotal=float(bill.subtotal or 0),
        gst_percent=float(bill.gst_percent or 0),
        gst_amount=float(bill.gst_amount or 0),
        grand_total=float(bill.grand_total or 0),
        payment_status=bill.payment_status,
        payment_mode=bill.payment_mode,
        paid_amount=float(bill.paid_amount or 0),
        balance_due=float(bill.balance_due or 0),
        status=bill.status,
        generated_at=_iso(bill.generated_at),
        items=[
            IpdBillItemOut(
                id=i.id,
                description=i.description,
                qty=i.qty,
                unit_price=float(i.unit_price),
                amount=float(i.amount),
                item_type=i.item_type,
            )
            for i in items
        ],
    )


def _non_void_bills(db: Session, admission_id: int) -> List[IpdBill]:
    return (
        db.query(IpdBill)
        .filter(
            IpdBill.admission_id == admission_id,
            IpdBill.status != "void",
        )
        .order_by(IpdBill.id.asc())
        .all()
    )


def _open_unpaid_bill(db: Session, admission_id: int) -> Optional[IpdBill]:
    return (
        db.query(IpdBill)
        .filter(
            IpdBill.admission_id == admission_id,
            IpdBill.status != "void",
            IpdBill.payment_status.in_(["pending", "partial"]),
        )
        .order_by(IpdBill.id.asc())
        .first()
    )


def _already_billed_total(db: Session, admission_id: int) -> float:
    """Grand total already captured on non-void bills (paid + open)."""
    return round(
        sum(float(b.grand_total or 0) for b in _non_void_bills(db, admission_id)),
        2,
    )


def _paid_towards_admission(db: Session, admission_id: int) -> float:
    return round(
        sum(float(b.paid_amount or 0) for b in _non_void_bills(db, admission_id)),
        2,
    )


def generate_bill(
    db: Session, data: IpdGenerateBillRequest, generated_by: int
) -> IpdBillOut:
    admission = h.get_admission(db, data.admission_id)
    if admission.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot bill a cancelled admission")

    open_bill = _open_unpaid_bill(db, admission.id)
    if open_bill:
        raise HTTPException(
            status_code=400,
            detail=f"Admission already has an unpaid bill ({open_bill.bill_number})",
        )

    preview_items, subtotal, _days = _charge_lines_for_admission(db, admission)
    for extra in data.extra_items or []:
        amount = round(extra.qty * extra.unit_price, 2)
        preview_items.append(
            {
                "description": extra.description,
                "qty": extra.qty,
                "unit_price": float(extra.unit_price),
                "amount": amount,
                "item_type": extra.item_type or "misc",
            }
        )
        subtotal = round(subtotal + amount, 2)

    pricing = opd_settings_service.get_pricing(db)
    gst_percent = (
        float(data.gst_percent)
        if data.gst_percent is not None
        else float(getattr(pricing, "gst_percent", None) or 0)
    )
    subtotal, gst_amount, grand = oh.bill_totals_from_subtotal(subtotal, gst_percent)

    already_billed = _already_billed_total(db, admission.id)
    due_to_bill = round(max(grand - already_billed, 0), 2)
    if due_to_bill <= 0.01:
        raise HTTPException(
            status_code=400,
            detail="No outstanding balance to bill — charges are already settled",
        )

    # After a paid bill, only generate the unpaid delta (avoid duplicate full bills)
    if already_billed > 0.01 and due_to_bill < grand - 0.01:
        if gst_percent > 0:
            net_subtotal = round(due_to_bill / (1 + (gst_percent / 100.0)), 2)
            gst_amount = round(due_to_bill - net_subtotal, 2)
            subtotal = net_subtotal
        else:
            subtotal = due_to_bill
            gst_amount = 0.0
        grand = due_to_bill
        preview_items = [
            {
                "description": "Additional IPD charges",
                "qty": 1,
                "unit_price": subtotal,
                "amount": subtotal,
                "item_type": "misc",
            }
        ]

    amount_received = float(data.amount_received or 0)
    pay_later = bool(data.pay_later)
    if not pay_later and amount_received > 0:
        mode = (data.payment_mode or "cash").strip().lower()
        oh.ensure_immediate_payment_valid(
            mode, pay_later=False, paid=amount_received, transaction_reference=data.transaction_reference
        )
    else:
        mode = (data.payment_mode or None)

    paid = 0.0 if pay_later else min(amount_received, grand)
    balance = round(max(grand - paid, 0), 2)
    payment_status = "paid" if balance <= 0 and grand > 0 else ("partial" if paid > 0 else "pending")
    if grand == 0:
        payment_status = "paid"

    bill = IpdBill(
        bill_number=h.next_ipd_bill_number(db),
        admission_id=admission.id,
        subtotal=subtotal,
        gst_percent=gst_percent,
        gst_amount=gst_amount,
        grand_total=grand,
        payment_status=payment_status,
        payment_mode=mode,
        paid_amount=paid,
        balance_due=balance,
        paid_at=h.now_ist() if paid > 0 else None,
        status="final",
        generated_by=generated_by,
        generated_at=h.now_ist(),
    )
    db.add(bill)
    db.flush()

    for item in preview_items:
        db.add(
            IpdBillItem(
                bill_id=bill.id,
                description=item["description"],
                qty=item["qty"],
                unit_price=item["unit_price"],
                amount=item["amount"],
                item_type=item.get("item_type") or "misc",
            )
        )

    if paid > 0:
        db.add(
            IpdPaymentTransaction(
                bill_id=bill.id,
                amount=paid,
                payment_mode=mode or "cash",
                transaction_reference=data.transaction_reference,
                paid_at=h.now_ist(),
                recorded_by=generated_by,
            )
        )

    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


def collect_payment(
    db: Session, bill_id: int, data: IpdCollectPaymentRequest, recorded_by: int
) -> IpdBillOut:
    bill = db.query(IpdBill).filter(IpdBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="IPD bill not found")
    if bill.status == "void":
        raise HTTPException(status_code=400, detail="Cannot pay a void bill")
    if bill.balance_due <= 0:
        raise HTTPException(status_code=400, detail="Bill is already fully paid")

    amount = float(data.amount)
    if amount > bill.balance_due + 0.01:
        raise HTTPException(status_code=400, detail="Amount exceeds balance due")

    mode = (data.payment_mode or "cash").strip().lower()
    if mode == "online":
        mode = "insurance"
    oh.ensure_immediate_payment_valid(
        mode, pay_later=False, paid=amount, transaction_reference=data.transaction_reference
    )

    db.add(
        IpdPaymentTransaction(
            bill_id=bill.id,
            amount=amount,
            payment_mode=mode,
            transaction_reference=data.transaction_reference,
            paid_at=h.now_ist(),
            recorded_by=recorded_by,
        )
    )
    new_paid = round((bill.paid_amount or 0) + amount, 2)
    bill.paid_amount = new_paid
    bill.payment_mode = mode
    bill.paid_at = h.now_ist()
    bill.balance_due = round(max(bill.grand_total - new_paid, 0), 2)
    bill.payment_status = "paid" if bill.balance_due <= 0 else "partial"

    db.commit()
    db.refresh(bill)
    return _bill_out(db, bill)


def list_running_bills(db: Session, page: int = 1, limit: int = 20) -> dict:
    """Active admissions with computed running totals (not yet fully paid)."""
    page = max(1, page)
    limit = min(max(1, limit), 100)
    q = db.query(IpdAdmission).filter(IpdAdmission.status == "admitted")
    total = q.count()
    rows = (
        q.order_by(IpdAdmission.admitted_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = []
    for adm in rows:
        preview = build_bill_preview(db, adm.id)
        unpaid = _open_unpaid_bill(db, adm.id)
        running_total = float(preview.grand_total or 0)
        paid_raw = _paid_towards_admission(db, adm.id)
        # Paid/Due are always relative to current running charges (never Paid > Total)
        if unpaid:
            due_balance = round(max(float(unpaid.balance_due or 0), 0), 2)
            paid_balance = round(max(running_total - due_balance, 0), 2)
            open_bill_id = unpaid.id
        else:
            paid_balance = round(min(max(paid_raw, 0), running_total), 2)
            due_balance = round(max(running_total - paid_balance, 0), 2)
            if due_balance <= 0.01:
                due_balance = 0.0
                paid_balance = running_total if running_total > 0 else 0.0
            open_bill_id = None

        items.append(
            {
                "admission": _admission_out(db, adm).model_dump(),
                "running_total": running_total,
                "balance": due_balance,
                "paid_amount": paid_balance,
                "open_bill_id": open_bill_id,
            }
        )
    return {"total": total, "page": page, "limit": limit, "items": items}


def _norm_payment_mode(mode: Optional[str]) -> str:
    key = (mode or "").strip().lower()
    if key == "upi":
        return "upi"
    if key == "online":
        return "insurance"
    if key in {"cash", "card", "insurance"}:
        return key
    return key or "cash"


def build_invoice(db: Session, bill_id: int) -> dict:
    """Full IPD invoice payload for view / print (mirrors OPD build_invoice)."""
    bill = db.query(IpdBill).filter(IpdBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="IPD bill not found")

    admission = h.get_admission(db, bill.admission_id)
    patient = db.query(Patient).filter(Patient.id == admission.patient_id).first()
    dept = (
        db.query(Department).filter(Department.id == admission.department_id).first()
        if admission.department_id
        else None
    )
    items = (
        db.query(IpdBillItem)
        .filter(IpdBillItem.bill_id == bill.id)
        .order_by(IpdBillItem.id.asc())
        .all()
    )
    txns = (
        db.query(IpdPaymentTransaction)
        .filter(IpdPaymentTransaction.bill_id == bill.id)
        .order_by(IpdPaymentTransaction.paid_at.asc())
        .all()
    )

    gst_pct = float(bill.gst_percent or 0)
    gst_label = f"Tax ({int(gst_pct)}% GST)" if gst_pct == int(gst_pct) else f"Tax ({gst_pct}% GST)"
    bill_date = bill.generated_at or bill.paid_at

    return {
        "hospital": {"name": "CarePoint Hospital", "address": "", "gstin": ""},
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "admission_id": admission.id,
        "admission_no": admission.admission_no,
        "bill_date": bill_date.strftime("%d %b %Y") if bill_date else "",
        "patient": {
            "name": h.display_name(patient.first_name, patient.last_name) if patient else "",
            "patient_id": patient.id if patient else None,
            "patient_uid": patient.patient_uid if patient else None,
            "phone": patient.phone if patient else None,
            "address": patient.address if patient else None,
        },
        "service": {
            "department": dept.name if dept else (admission.ward_name or "IPD"),
            "doctor": _admission_doctor_name(db, admission) or "",
            "ward": admission.ward_name,
            "bed": admission.bed_number,
            "admission_no": admission.admission_no,
        },
        "bill_items": [
            {
                "description": i.description,
                "qty": i.qty,
                "unit_price": float(i.unit_price),
                "amount": float(i.amount),
            }
            for i in items
        ],
        "payment_history": [
            {
                "date": t.paid_at.strftime("%d %b %Y") if t.paid_at else "",
                "mode": _norm_payment_mode(t.payment_mode),
                "ref": t.transaction_reference or "—",
                "amount": float(t.amount),
            }
            for t in txns
        ],
        "summary": {
            "subtotal": float(bill.subtotal or 0),
            "gst_label": gst_label,
            "gst_amount": float(bill.gst_amount or 0),
            "grand_total": float(bill.grand_total or 0),
            "amount_paid": float(bill.paid_amount or 0),
            "balance_due": float(bill.balance_due or 0),
            "payment_mode": bill.payment_mode,
            "payment_status": bill.payment_status,
        },
    }


def payment_history(
    db: Session,
    *,
    search: Optional[str] = None,
    payment_mode: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    page = max(1, page)
    limit = min(max(1, limit), 100)
    q = (
        db.query(IpdPaymentTransaction, IpdBill, IpdAdmission, Patient)
        .join(IpdBill, IpdPaymentTransaction.bill_id == IpdBill.id)
        .join(IpdAdmission, IpdBill.admission_id == IpdAdmission.id)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
        .order_by(IpdPaymentTransaction.paid_at.desc())
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Patient.first_name.ilike(term))
            | (Patient.last_name.ilike(term))
            | (Patient.patient_uid.ilike(term))
            | (IpdBill.bill_number.ilike(term))
            | (IpdAdmission.admission_no.ilike(term))
            | (IpdPaymentTransaction.transaction_reference.ilike(term))
        )

    all_rows = q.all()
    by_mode: dict[str, float] = {"cash": 0.0, "upi": 0.0, "card": 0.0, "insurance": 0.0}
    total_collected = 0.0
    for txn, _, _, _ in all_rows:
        amount = float(txn.amount or 0)
        total_collected += amount
        mode = _norm_payment_mode(txn.payment_mode)
        by_mode[mode] = by_mode.get(mode, 0.0) + amount

    filtered = all_rows
    if payment_mode:
        want = _norm_payment_mode(payment_mode)
        filtered = [
            row for row in all_rows if _norm_payment_mode(row[0].payment_mode) == want
        ]

    page_rows = filtered[(page - 1) * limit : page * limit]
    items = []
    for txn, bill, adm, patient in page_rows:
        items.append(
            {
                "id": txn.id,
                "paid_at": _iso(txn.paid_at),
                "receipt_no": f"IPD-RCPT-{txn.id:05d}",
                "amount": float(txn.amount),
                "mode": _norm_payment_mode(txn.payment_mode),
                "reference": txn.transaction_reference,
                "bill_id": bill.id,
                "bill_number": bill.bill_number,
                "bill_balance": float(bill.balance_due or 0),
                "admission_id": adm.id,
                "admission_no": adm.admission_no,
                "patient_name": h.display_name(patient.first_name, patient.last_name),
                "patient_uid": patient.patient_uid,
            }
        )
    return {
        "summary": {
            "total_collected": round(total_collected, 2),
            "cash": round(by_mode.get("cash", 0), 2),
            "upi": round(by_mode.get("upi", 0), 2),
            "card": round(by_mode.get("card", 0), 2),
            "insurance": round(by_mode.get("insurance", 0), 2),
            "transaction_count": len(all_rows),
        },
        "total": len(filtered),
        "page": page,
        "limit": limit,
        "items": items,
    }


def discharge_patient(
    db: Session, admission_id: int, data: IpdDischargeRequest, discharged_by: int
) -> dict:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Admission is not active")

    unpaid = _open_unpaid_bill(db, admission.id)
    if unpaid and not data.force:
        raise HTTPException(
            status_code=400,
            detail=f"Settle bill {unpaid.bill_number} (balance {unpaid.balance_due}) before discharge",
        )

    # Bill any uncovered running charges (first bill or post-payment delta)
    bill_out = None
    preview = build_bill_preview(db, admission.id)
    due = round(
        max(float(preview.grand_total or 0) - _paid_towards_admission(db, admission.id), 0),
        2,
    )
    if due > 0.01:
        try:
            bill_out = generate_bill(
                db,
                IpdGenerateBillRequest(admission_id=admission.id, pay_later=True),
                generated_by=discharged_by,
            )
        except HTTPException as exc:
            detail = str(getattr(exc, "detail", "") or "")
            if "No outstanding balance" not in detail:
                raise
        unpaid = _open_unpaid_bill(db, admission.id)
        if unpaid and not data.force:
            raise HTTPException(
                status_code=400,
                detail=f"Bill {unpaid.bill_number} generated — collect payment before discharge",
            )

    if admission.bed_id:
        bed = h.get_bed(db, admission.bed_id)
        h.free_bed(db, bed)

    admission.status = "discharged"
    admission.discharged_at = h.now_ist()
    admission.discharged_by = discharged_by
    if data.notes:
        admission.notes = (
            f"{admission.notes}\nDischarge: {data.notes}".strip()
            if admission.notes
            else f"Discharge: {data.notes}"
        )

    db.commit()
    db.refresh(admission)
    return {
        "admission": _admission_out(db, admission).model_dump(),
        "bill": bill_out.model_dump() if bill_out else None,
        "message": "Patient discharged",
    }


def get_dashboard(db: Session) -> dict:
    beds = bed_service.list_beds(db)
    stats = beds.get("stats") or {}
    today = h.now_ist().date()
    from sqlalchemy import cast, Date

    admissions_today = (
        db.query(IpdAdmission)
        .filter(cast(IpdAdmission.admitted_at, Date) == today)
        .count()
    )
    pending_discharges = (
        db.query(IpdAdmission).filter(IpdAdmission.status == "admitted").count()
    )
    running_bills = (
        db.query(IpdBill)
        .filter(IpdBill.payment_status.in_(["pending", "partial"]))
        .count()
    )
    recent = (
        db.query(IpdAdmission)
        .filter(IpdAdmission.status == "admitted")
        .order_by(IpdAdmission.admitted_at.desc())
        .limit(8)
        .all()
    )
    return {
        "occupied_beds": stats.get("occupied", 0),
        "available_beds": stats.get("available", 0),
        "total_beds": stats.get("total", 0),
        "admissions_today": admissions_today,
        "pending_discharges": pending_discharges,
        "running_bills": running_bills,
        "ward_stats": bed_service.get_ward_bed_stats(db),
        "recent_admissions": [_admission_out(db, r).model_dump() for r in recent],
    }


def _enrich_bed_for_ipd(db: Session, bed_out) -> dict:
    """Attach display-only bed rate when Admin set a special_bed_rates override."""
    payload = bed_out.model_dump() if hasattr(bed_out, "model_dump") else dict(bed_out)
    pricing = opd_settings_service.get_pricing(db)
    special_rate = opd_settings_service.get_special_bed_rate(
        pricing,
        bed_number=payload.get("bed_number"),
    )
    payload["charge_per_day"] = special_rate
    payload["has_custom_rate"] = special_rate is not None
    return payload


def list_beds(db: Session, ward: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None):
    payload = bed_service.list_beds(db, ward=ward, status=status, search=search)
    payload["beds"] = [_enrich_bed_for_ipd(db, bed) for bed in payload.get("beds", [])]
    return payload


def ward_stats(db: Session):
    pricing = opd_settings_service.get_pricing(db)
    wards = []
    for row in bed_service.get_ward_bed_stats(db):
        ward_name = row.get("ward")
        wards.append(
            {
                **row,
                "charge_per_day": float(
                    opd_settings_service.resolve_bed_rate(
                        pricing,
                        ward_name=ward_name,
                    )
                ),
            }
        )
    return {"wards": wards}
