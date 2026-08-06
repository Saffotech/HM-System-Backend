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

    visit = IpdDoctorVisit(
        admission_id=admission.id,
        doctor_id=data.doctor_id,
        visited_at=_parse_dt(data.visited_at),
        charge=float(data.charge),
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


def generate_bill(
    db: Session, data: IpdGenerateBillRequest, generated_by: int
) -> IpdBillOut:
    admission = h.get_admission(db, data.admission_id)
    if admission.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot bill a cancelled admission")

    open_bill = (
        db.query(IpdBill)
        .filter(
            IpdBill.admission_id == admission.id,
            IpdBill.status == "final",
            IpdBill.payment_status.in_(["pending", "partial"]),
        )
        .first()
    )
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
        unpaid = (
            db.query(IpdBill)
            .filter(
                IpdBill.admission_id == adm.id,
                IpdBill.payment_status.in_(["pending", "partial"]),
            )
            .first()
        )
        items.append(
            {
                "admission": _admission_out(db, adm).model_dump(),
                "running_total": preview.grand_total,
                "balance": float(unpaid.balance_due) if unpaid else preview.grand_total,
                "open_bill_id": unpaid.id if unpaid else None,
            }
        )
    return {"total": total, "page": page, "limit": limit, "items": items}


def payment_history(
    db: Session,
    *,
    search: Optional[str] = None,
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
    total = q.count()
    rows = (
        q.order_by(IpdPaymentTransaction.paid_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = []
    for txn, bill, adm, patient in rows:
        items.append(
            {
                "id": txn.id,
                "paid_at": _iso(txn.paid_at),
                "receipt_no": f"IPD-RCPT-{txn.id:05d}",
                "amount": float(txn.amount),
                "mode": txn.payment_mode,
                "reference": txn.transaction_reference,
                "bill_number": bill.bill_number,
                "admission_id": adm.id,
                "admission_no": adm.admission_no,
                "patient_name": h.display_name(patient.first_name, patient.last_name),
                "patient_uid": patient.patient_uid,
            }
        )
    return {"total": total, "page": page, "limit": limit, "items": items}


def discharge_patient(
    db: Session, admission_id: int, data: IpdDischargeRequest, discharged_by: int
) -> dict:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Admission is not active")

    unpaid = (
        db.query(IpdBill)
        .filter(
            IpdBill.admission_id == admission.id,
            IpdBill.payment_status.in_(["pending", "partial"]),
        )
        .first()
    )
    if unpaid and not data.force:
        raise HTTPException(
            status_code=400,
            detail=f"Settle bill {unpaid.bill_number} (balance {unpaid.balance_due}) before discharge",
        )

    # If no bill exists yet, auto-generate a final bill (pay later) so history is complete
    any_bill = db.query(IpdBill).filter(IpdBill.admission_id == admission.id).first()
    bill_out = None
    if not any_bill:
        bill_out = generate_bill(
            db,
            IpdGenerateBillRequest(admission_id=admission.id, pay_later=True),
            generated_by=discharged_by,
        )
        unpaid = (
            db.query(IpdBill)
            .filter(
                IpdBill.admission_id == admission.id,
                IpdBill.payment_status.in_(["pending", "partial"]),
            )
            .first()
        )
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


def list_beds(db: Session, ward: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None):
    return bed_service.list_beds(db, ward=ward, status=status, search=search)


def ward_stats(db: Session):
    return {"wards": bed_service.get_ward_bed_stats(db)}
