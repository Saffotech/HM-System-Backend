"""OPD & billing — patients, visits, bills, payments, dashboard."""
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.department import Department
from Models.opd_billing import BillItem, PaymentTransaction
from Models.patient import OpdVisit, Patient
from Models.user import User
from Schemas.opd_schema import (
    BillLineItem,
    BillListItem,
    BillPreviewRequest,
    BillPreviewResponse,
    BillSummary,
    CollectPayment,
    GenerateBillRequest,
    OpdVisitCreate,
    PatientRegisterRequest,
    QueueResponse,
    QueueVisitItem,
    RegisterSuccessResponse,
    VisitBillingFields,
    VisitSuccessResponse,
)
from Schemas.patient_schema import PatientOut, PatientUpdate, gender_code_to_label
from Services import opd_helpers as h

# Re-export helpers used by router
get_patient = h.get_patient
list_doctors_in_department = h.list_doctors_in_department
display_name = h.display_name


def build_bill_preview(data: BillPreviewRequest) -> BillPreviewResponse:
    subtotal, gst_amount, grand_total = h.bill_totals(
        data.registration_fee, data.consultation_fee, data.gst_percent
    )
    return BillPreviewResponse(
        bill_items=[
            BillLineItem(description="Registration Fee", qty=1, unit_price=data.registration_fee, amount=data.registration_fee),
            BillLineItem(description="Doctor Consultation", qty=1, unit_price=data.consultation_fee, amount=data.consultation_fee),
        ],
        summary=BillSummary(subtotal=subtotal, gst_percent=data.gst_percent, gst_amount=gst_amount, grand_total=grand_total),
    )


def patient_to_model(data: PatientRegisterRequest, patient_uid: str, registered_by: int) -> Patient:
    return Patient(
        patient_uid=patient_uid,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        gender=gender_code_to_label(data.gender),
        blood_group=data.blood_group,
        phone=data.phone,
        email=data.email,
        address=data.address,
        state=data.state,
        aadhaar_number=data.aadhaar_number,
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=data.emergency_contact_phone,
        allergies=data.allergies,
        insurance_policy_no=data.insurance_policy_no,
        registered_by=registered_by,
    )


def create_visit(
    db: Session,
    patient: Patient,
    billing: VisitBillingFields,
    registered_by: int,
    *,
    pay_later: bool = False,
    payment_mode: str = "cash",
    amount_received: Optional[float] = None,
    extra_items: Optional[List[dict]] = None,
) -> OpdVisit:
    h.get_department(db, billing.department_id)
    doctor = h.get_doctor_in_department(db, billing.doctor_id, billing.department_id)

    subtotal = billing.registration_fee + billing.consultation_fee
    if extra_items:
        for item in extra_items:
            subtotal += round(item["qty"] * item["unit_price"], 2)

    subtotal, gst_amount, grand_total = h.bill_totals_from_subtotal(subtotal, billing.gst_percent)
    bill_number, token_number = h.next_visit_numbers(db)

    if pay_later:
        paid, status, balance = 0.0, "pending", grand_total
    else:
        paid = amount_received if amount_received is not None else grand_total
        balance = round(max(grand_total - paid, 0), 2)
        status = "paid" if balance <= 0 else "partial"

    visit = OpdVisit(
        bill_number=bill_number,
        token_number=token_number,
        patient_id=patient.id,
        department_id=billing.department_id,
        doctor_id=billing.doctor_id,
        registration_fee=billing.registration_fee,
        consultation_fee=billing.consultation_fee,
        subtotal=subtotal,
        gst_percent=billing.gst_percent,
        gst_amount=gst_amount,
        grand_total=grand_total,
        payment_status=status,
        payment_mode=payment_mode if paid > 0 else None,
        paid_amount=paid if paid > 0 else None,
        balance_due=balance,
        paid_at=h.now_ist() if paid > 0 else None,
        status="doctor_assigned",
        registered_by=registered_by,
    )
    db.add(visit)
    db.flush()

    h.save_default_bill_items(db, visit, doctor)
    if extra_items:
        h.save_extra_bill_items(db, visit.id, extra_items)

    if paid > 0:
        h.record_payment(db, visit, paid, payment_mode, registered_by)

    return visit


def register_new_patient(
    db: Session,
    data: PatientRegisterRequest,
    registered_by: int,
    payment_mode: str = "cash",
    pay_later: bool = False,
    amount_received: Optional[float] = None,
) -> RegisterSuccessResponse:
    if not pay_later:
        h.validate_payment_mode(payment_mode)

    existing = db.query(Patient).filter(Patient.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Patient already exists. UID: {existing.patient_uid}")

    patient = patient_to_model(data, h.next_patient_uid(db), registered_by)
    db.add(patient)
    db.flush()

    visit = create_visit(
        db, patient, data, registered_by,
        pay_later=pay_later,
        payment_mode=payment_mode,
        amount_received=amount_received,
    )
    db.commit()
    db.refresh(visit)

    return RegisterSuccessResponse(
        message="Patient registered successfully",
        patient_id=patient.patient_uid,
        bill_number=visit.bill_number,
        token_number=visit.token_number,
        visit_id=visit.id,
    )


def create_visit_for_existing_patient(
    db: Session,
    data: OpdVisitCreate,
    registered_by: int,
    payment_mode: str = "cash",
    pay_later: bool = False,
    amount_received: Optional[float] = None,
) -> VisitSuccessResponse:
    if not pay_later:
        h.validate_payment_mode(payment_mode)

    patient = h.get_patient(db, data.patient_id)
    billing = data.model_copy(update={"registration_fee": 0.0}) if data.waive_registration_fee else data

    visit = create_visit(
        db, patient, billing, registered_by,
        pay_later=pay_later,
        payment_mode=payment_mode,
        amount_received=amount_received,
    )
    db.commit()
    db.refresh(visit)

    return VisitSuccessResponse(
        message="OPD visit created successfully",
        patient_id=patient.patient_uid,
        bill_number=visit.bill_number,
        token_number=visit.token_number,
        visit_id=visit.id,
        grand_total=visit.grand_total,
        payment_status=visit.payment_status,
    )


def generate_bill(
    db: Session, data: GenerateBillRequest, registered_by: int
) -> VisitSuccessResponse:
    patient = h.get_patient(db, data.patient_id)
    extra = [{"description": i.description, "qty": i.qty, "unit_price": i.unit_price} for i in data.extra_items]

    billing = VisitBillingFields(
        department_id=data.department_id,
        doctor_id=data.doctor_id,
        registration_fee=data.registration_fee,
        consultation_fee=data.consultation_fee,
        gst_percent=data.gst_percent,
    )
    visit = create_visit(
        db, patient, billing, registered_by,
        pay_later=data.pay_later,
        payment_mode=data.payment_mode,
        amount_received=data.amount_received,
        extra_items=extra or None,
    )
    db.commit()
    db.refresh(visit)

    return VisitSuccessResponse(
        message="Bill generated successfully",
        patient_id=patient.patient_uid,
        bill_number=visit.bill_number,
        token_number=visit.token_number,
        visit_id=visit.id,
        grand_total=visit.grand_total,
        payment_status=visit.payment_status,
    )


def list_patients(db: Session, search: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
    q = db.query(Patient).filter(Patient.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Patient.first_name.ilike(term))
            | (Patient.last_name.ilike(term))
            | (Patient.phone.ilike(term))
            | (Patient.patient_uid.ilike(term))
        )
    total = q.count()
    rows = q.order_by(Patient.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"total": total, "page": page, "limit": limit, "patients": [PatientOut.model_validate(p) for p in rows]}


def get_patient_profile(db: Session, patient_id: int) -> dict:
    patient = h.get_patient(db, patient_id)
    visits = (
        db.query(OpdVisit)
        .filter(OpdVisit.patient_id == patient_id)
        .order_by(OpdVisit.visit_date.desc())
        .limit(20)
        .all()
    )

    total_billed = sum(v.grand_total for v in visits)
    total_paid = sum(v.paid_amount or 0 for v in visits)
    outstanding = sum(v.balance_due for v in visits)

    visit_rows = []
    for v in visits:
        doctor = db.query(User).filter(User.id == v.doctor_id).first()
        dept = db.query(Department).filter(Department.id == v.department_id).first()
        visit_rows.append({
            "visit_id": v.id,
            "bill_number": v.bill_number,
            "token_number": v.token_number,
            "visit_date": v.visit_date.isoformat() if v.visit_date else None,
            "doctor_name": h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. ") if doctor else None,
            "department": dept.name if dept else None,
            "grand_total": v.grand_total,
            "paid_amount": v.paid_amount,
            "balance_due": v.balance_due,
            "payment_status": v.payment_status,
            "status": v.status,
        })

    return {
        "patient": PatientOut.model_validate(patient),
        "summary": {
            "total_visits": len(visits),
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "outstanding": round(outstanding, 2),
        },
        "visits": visit_rows,
    }


def update_patient(db: Session, patient_id: int, data: PatientUpdate) -> PatientOut:
    patient = h.get_patient(db, patient_id)
    updates = data.model_dump(exclude_unset=True)

    if "phone" in updates and updates["phone"] != patient.phone:
        if db.query(Patient).filter(Patient.phone == updates["phone"], Patient.id != patient_id).first():
            raise HTTPException(status_code=409, detail="Phone number already in use")

    if "gender" in updates:
        updates["gender"] = gender_code_to_label(updates.pop("gender"))

    for key, value in updates.items():
        setattr(patient, key, value)

    db.commit()
    db.refresh(patient)
    return PatientOut.model_validate(patient)


def delete_patient(db: Session, patient_id: int) -> dict:
    patient = h.get_patient(db, patient_id)
    patient.is_active = False
    db.commit()
    return {"message": "Patient deactivated", "patient_uid": patient.patient_uid}


def build_invoice(db: Session, visit_id: int) -> dict:
    visit, patient, doctor, dept = h.get_visit_with_relations(db, visit_id)
    items = h.list_bill_items(db, visit_id)
    if not items:
        items_data = [
            {"description": "Registration Fee", "qty": 1, "unit_price": visit.registration_fee, "amount": visit.registration_fee},
            {"description": "Consultation", "qty": 1, "unit_price": visit.consultation_fee, "amount": visit.consultation_fee},
        ]
    else:
        items_data = [
            {"description": i.description, "qty": i.qty, "unit_price": i.unit_price, "amount": i.amount}
            for i in items
        ]

    history = h.payment_history_rows(db, visit_id)
    if not history and visit.paid_amount:
        history = [{
            "date": visit.paid_at.strftime("%d %b %Y") if visit.paid_at else "",
            "mode": visit.payment_mode,
            "ref": "—",
            "amount": visit.paid_amount,
        }]

    return {
        "hospital": {"name": "CarePoint Hospital", "address": "", "gstin": ""},
        "bill_number": visit.bill_number,
        "token_number": visit.token_number,
        "visit_date": visit.visit_date.strftime("%d %b %Y") if visit.visit_date else "",
        "patient": {
            "name": h.display_name(patient.first_name, patient.last_name),
            "patient_id": patient.patient_uid,
            "phone": patient.phone,
            "address": patient.address,
        },
        "service": {
            "department": dept.name if dept else "",
            "doctor": h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. ") if doctor else "",
        },
        "bill_items": items_data,
        "payment_history": history,
        "summary": {
            "subtotal": visit.subtotal,
            "gst_label": f"Tax ({int(visit.gst_percent)}% GST)",
            "gst_amount": visit.gst_amount,
            "grand_total": visit.grand_total,
            "amount_paid": visit.paid_amount or 0,
            "balance_due": visit.balance_due,
            "payment_mode": visit.payment_mode,
            "payment_status": visit.payment_status,
        },
    }


def _bills_query(db: Session, status, search, today_only, from_date, to_date):
    q = db.query(OpdVisit, Patient).join(Patient, OpdVisit.patient_id == Patient.id)
    if status:
        q = q.filter(OpdVisit.payment_status == status)
    if today_only:
        q = q.filter(OpdVisit.visit_date >= h.today_start_ist())
    if from_date:
        q = q.filter(OpdVisit.visit_date >= from_date)
    if to_date:
        q = q.filter(OpdVisit.visit_date <= to_date)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Patient.first_name.ilike(term))
            | (Patient.last_name.ilike(term))
            | (Patient.patient_uid.ilike(term))
            | (OpdVisit.bill_number.ilike(term))
            | (OpdVisit.token_number.ilike(term))
        )
    return q


def list_bills(
    db: Session,
    status: Optional[str] = None,
    search: Optional[str] = None,
    today_only: bool = False,
    from_date=None,
    to_date=None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q = _bills_query(db, status, search, today_only, from_date, to_date)
    all_rows = q.all()
    total_billed = sum(v.grand_total for v, _ in all_rows)
    total_collected = sum(v.paid_amount or 0 for v, _ in all_rows)
    total_outstanding = sum(v.balance_due for v, _ in all_rows)

    total = len(all_rows)
    rows = all_rows[(page - 1) * limit : page * limit]

    bills = [
        BillListItem(
            visit_id=visit.id,
            bill_number=visit.bill_number,
            token_number=visit.token_number,
            patient_uid=patient.patient_uid,
            patient_name=h.display_name(patient.first_name, patient.last_name),
            grand_total=visit.grand_total,
            paid_amount=visit.paid_amount,
            balance_due=visit.balance_due,
            payment_status=visit.payment_status,
            visit_date=visit.visit_date.isoformat() if visit.visit_date else None,
        )
        for visit, patient in rows
    ]

    rate = round((total_collected / total_billed * 100), 1) if total_billed else 0
    return {
        "summary": {
            "total_billed": round(total_billed, 2),
            "total_collected": round(total_collected, 2),
            "total_outstanding": round(total_outstanding, 2),
            "collection_rate_percent": rate,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "bills": bills,
    }


def collect_payment(db: Session, visit_id: int, data: CollectPayment, recorded_by: int) -> dict:
    visit, patient, _, _ = h.get_visit_with_relations(db, visit_id)
    if visit.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Bill is already fully paid")
    if data.paid_amount > visit.balance_due + 0.01:
        raise HTTPException(status_code=400, detail=f"Amount exceeds balance due ({visit.balance_due})")

    h.record_payment(db, visit, data.paid_amount, data.payment_mode, recorded_by, data.transaction_reference)
    db.commit()
    db.refresh(visit)

    return {
        "message": "Payment recorded",
        "bill_number": visit.bill_number,
        "patient_id": patient.patient_uid,
        "amount_paid": data.paid_amount,
        "total_paid": visit.paid_amount,
        "balance_due": visit.balance_due,
        "payment_status": visit.payment_status,
    }


def list_payment_history(
    db: Session,
    search: Optional[str] = None,
    payment_mode: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q = (
        db.query(PaymentTransaction, OpdVisit, Patient)
        .join(OpdVisit, PaymentTransaction.visit_id == OpdVisit.id)
        .join(Patient, OpdVisit.patient_id == Patient.id)
        .order_by(PaymentTransaction.paid_at.desc())
    )
    if payment_mode:
        q = q.filter(PaymentTransaction.payment_mode == payment_mode)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            (Patient.patient_uid.ilike(term))
            | (OpdVisit.bill_number.ilike(term))
            | (PaymentTransaction.transaction_reference.ilike(term))
        )

    rows = q.all()
    total_collected = sum(t.amount for t, _, _ in rows)
    by_mode = {}
    for t, _, _ in rows:
        by_mode[t.payment_mode] = by_mode.get(t.payment_mode, 0) + t.amount

    page_rows = rows[(page - 1) * limit : page * limit]
    return {
        "summary": {
            "total_collected": round(total_collected, 2),
            "cash": round(by_mode.get("cash", 0), 2),
            "upi": round(by_mode.get("upi", 0), 2),
            "card": round(by_mode.get("card", 0), 2),
        },
        "total": len(rows),
        "page": page,
        "limit": limit,
        "payments": [
            {
                "id": t.id,
                "patient_name": h.display_name(p.first_name, p.last_name),
                "patient_uid": p.patient_uid,
                "bill_number": v.bill_number,
                "date": t.paid_at.isoformat() if t.paid_at else None,
                "mode": t.payment_mode,
                "amount": t.amount,
                "reference": t.transaction_reference,
                "bill_status": v.payment_status,
                "visit_id": v.id,
            }
            for t, v, p in page_rows
        ],
    }


def get_dashboard(db: Session) -> dict:
    today = h.today_start_ist()
    visits_today = db.query(OpdVisit).filter(OpdVisit.visit_date >= today).count()
    patients_total = db.query(Patient).filter(Patient.is_active.is_(True)).count()
    pending_bills = db.query(OpdVisit).filter(OpdVisit.payment_status.in_(["pending", "partial"])).count()

    from Models.opd_billing import Appointment, Bed

    appointments_today = db.query(Appointment).filter(
        Appointment.scheduled_at >= today,
        Appointment.status == "scheduled",
    ).count()
    beds_free = db.query(Bed).filter(Bed.status == "available").count()
    beds_total = db.query(Bed).count()

    recent = fetch_today_queue(db)
    return {
        "visits_today": visits_today,
        "patients_total": patients_total,
        "pending_bills": pending_bills,
        "appointments_today": appointments_today,
        "beds_free": beds_free,
        "beds_total": beds_total,
        "recent_visits": recent.visits[:5],
    }


def fetch_today_queue(db: Session) -> QueueResponse:
    rows = (
        db.query(OpdVisit, Patient, User, Department)
        .join(Patient, OpdVisit.patient_id == Patient.id)
        .outerjoin(User, OpdVisit.doctor_id == User.id)
        .outerjoin(Department, OpdVisit.department_id == Department.id)
        .filter(OpdVisit.visit_date >= h.today_start_ist())
        .order_by(OpdVisit.visit_date.asc())
        .all()
    )
    visits = [
        QueueVisitItem(
            visit_id=v.id,
            token_number=v.token_number,
            bill_number=v.bill_number,
            visit_date=v.visit_date.isoformat() if v.visit_date else None,
            patient_id=p.patient_uid,
            patient_name=h.display_name(p.first_name, p.last_name),
            doctor_name=h.display_name(d.first_name, d.last_name, prefix="Dr. ") if d else None,
            department=dept.name if dept else None,
            status=v.status,
            payment_status=v.payment_status,
            grand_total=v.grand_total,
            payment_mode=v.payment_mode,
        )
        for v, p, d, dept in rows
    ]
    return QueueResponse(total=len(visits), visits=visits)


def search_patient_by_phone(db: Session, phone: str) -> dict:
    patient = db.query(Patient).filter(Patient.phone == phone, Patient.is_active.is_(True)).first()
    if not patient:
        return {"found": False, "message": "New patient. Please register."}
    return {
        "found": True,
        "patient_id": patient.id,
        "patient_uid": patient.patient_uid,
        "name": h.display_name(patient.first_name, patient.last_name),
        "phone": patient.phone,
        "blood_group": patient.blood_group,
        "gender": patient.gender,
        "aadhaar": patient.aadhaar_number,
    }
