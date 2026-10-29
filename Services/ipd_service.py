"""IPD admissions, beds, visits, billing, discharge, and dashboard."""
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import or_ , func
from sqlalchemy.orm import Session, selectinload

from Models.department import Department
from Models.doctor_lab_test_order import LabTestOrder, LabTestStatus
from Models.ipd import (
    IpdAdmission,
    IpdAdmissionBilling,
    IpdAdmissionCareTeam,
    IpdBill,
    IpdBillItem,
    IpdDoctorVisit,
    IpdInsuranceClaim,
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
    IpdCareTeamAddRequest,
    IpdCareTeamMemberOut,
    IpdCollectPaymentRequest,
    IpdDischargeRequest,
    IpdDoctorVisitCreate,
    IpdDoctorVisitOut,
    IpdGenerateBillRequest,
    IpdTransferBedRequest,
)
from Services import bed_service
from Services import hospital_settings_service
from Services import ipd_helpers as h
from Services import opd_helpers as oh
from Services import opd_settings_service
from Services.ipd_notification_helpers import (
    notify_doctor_ipd_admitted,
    notify_doctors_ipd_care_team_added,
    notify_doctors_ipd_care_team_removed,
    notify_nurses_ipd_bed_patient,
)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return h.now_ist()
    try:
        raw = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return dt
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime format") from exc


def _ist_date(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return dt.astimezone(ZoneInfo("Asia/Kolkata")).date()


def _ensure_admission_date_in_range(admitted_at: datetime, patient: Patient) -> None:
    """Stay must start on or after the patient was registered, and not after today (IST)."""
    day = _ist_date(admitted_at)
    if day > _ist_date(h.now_ist()):
        raise HTTPException(
            status_code=400,
            detail="Admission date cannot be in the future",
        )
    registered = getattr(patient, "created_at", None)
    if registered is not None and day < _ist_date(registered):
        raise HTTPException(
            status_code=400,
            detail="Admission date is before the permitted minimum",
        )


def _admission_doctor_name(db: Session, row: IpdAdmission) -> Optional[str]:
    if row.doctor_id:
        return h.doctor_display(db, row.doctor_id)
    visit = (
        db.query(IpdDoctorVisit)
        .filter(
            IpdDoctorVisit.admission_id == row.id,
            IpdDoctorVisit.is_voided.is_(False),
        )
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
    days = _bed_days_for_admission(row)
    claim = (
        db.query(IpdInsuranceClaim)
        .filter(IpdInsuranceClaim.admission_id == row.id)
        .first()
    )
    payment_type = getattr(row, "payment_type", None) or "self"
    coverage = None
    insurer = None
    policy_no = None
    claim_id = None
    if claim:
        claim_id = claim.id
        insurer = claim.insurer
        policy_no = claim.policy_no
        coverage = (
            "Cashless Insurance" if claim.claim_type == "cashless" else "Copay"
        )
        if payment_type == "self":
            payment_type = (
                "insurance_cashless"
                if claim.claim_type == "cashless"
                else "insurance_copay"
            )
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
        payment_type=payment_type,
        self_pay_method=getattr(row, "self_pay_method", None),
        claim_id=claim_id,
        coverage=coverage,
        insurer=insurer,
        policy_no=policy_no,
        admitted_at=_iso(row.admitted_at),
        discharged_at=_iso(row.discharged_at),
        length_of_stay_days=days,
    )


def admit_patient(db: Session, data: IpdAdmitRequest, admitted_by: int) -> IpdAdmissionOut:
    from Services import ipd_insurance_service as ins

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

    payment_type, self_pay_method = ins.resolve_admit_payment(
        data.payment_mode,
        data.self_pay_method,
        data.insurance,
    )

    admitted_at = _parse_dt(data.admission_date)
    _ensure_admission_date_in_range(admitted_at, patient)

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
        payment_type=payment_type,
        self_pay_method=self_pay_method,
        admitted_at=admitted_at,
        admitted_by=admitted_by,
    )
    # Align bed.admitted_at with admission start for tariff day calc consistency
    bed.admitted_at = admission.admitted_at

    db.add(admission)
    db.flush()

    if data.insurance:
        ins.create_claim_for_admission(
            db,
            admission=admission,
            insurance=data.insurance,
            created_by=admitted_by,
        )

    db.commit()
    db.refresh(admission)
    notify_doctor_ipd_admitted(db, admission, created_by=admitted_by)
    notify_nurses_ipd_bed_patient(
        db,
        admission,
        created_by=admitted_by,
        exclude_user_ids={admission.doctor_id} if admission.doctor_id else None,
    )
    return _admission_out(db, admission)


def update_admission(
    db: Session,
    admission_id: int,
    data: IpdAdmissionUpdate,
    updated_by: Optional[int] = None,
) -> IpdAdmissionOut:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(status_code=400, detail="Only active admissions can be updated")

    previous_doctor_id = admission.doctor_id
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
    if admission.doctor_id and admission.doctor_id != previous_doctor_id:
        notify_doctor_ipd_admitted(db, admission, created_by=updated_by)
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
    old_bed_id = old_bed.id if old_bed else None

    h.occupy_bed(db, new_bed, admission.patient_id, admission.department_id)
    # Keep stay start for billing; occupancy timestamp on new bed is now
    new_bed.admitted_at = admission.admitted_at
    h.free_bed(db, old_bed)

    admission.bed_id = new_bed.id
    admission.ward_name = new_bed.ward_name
    admission.bed_number = new_bed.bed_number

    db.commit()
    db.refresh(admission)
    notify_nurses_ipd_bed_patient(
        db,
        admission,
        created_by=transferred_by,
        intro="A patient was transferred to your allocated bed.",
    )
    if old_bed_id:
        dest = f"{admission.ward_name or '—'} / {admission.bed_number or '—'}"
        notify_nurses_ipd_bed_patient(
            db,
            admission,
            created_by=transferred_by,
            bed_id=old_bed_id,
            exclude_user_ids=set(h.allocated_nurse_ids_for_bed(db, admission.bed_id)),
            title="Patient transferred from your bed",
            intro=f"A patient on your allocated bed was transferred to {dest}.",
        )
    return _admission_out(db, admission)


def admission_text_search_filter(search: str, *extra_columns):
    """P- matches only the patient ID. IPD- matches only the admission number.

    A bare number is not an ID search, so 1028 cannot match both P-1028 and IPD-1028.
    """
    raw = (search or "").strip()
    key = raw.upper()
    if key.startswith("P-"):
        return Patient.patient_uid.ilike(f"%{raw}%")
    if key.startswith("IPD-"):
        return IpdAdmission.admission_no.ilike(f"%{raw}%")
    term = f"%{raw}%"
    full_name = func.concat_ws(Patient.first_name," ",Patient.last_name)
    clauses = [
        full_name.ilike(term),
        Patient.first_name.ilike(term),
        Patient.last_name.ilike(term),
        Patient.phone.ilike(term),
        *[column.ilike(term) for column in extra_columns],
    ]
    return or_(*clauses)


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

    if search and search.strip():
        q = q.join(Patient, IpdAdmission.patient_id == Patient.id).filter(
            admission_text_search_filter(search, IpdAdmission.bed_number)
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
        .filter(
            IpdDoctorVisit.admission_id == admission.id,
            IpdDoctorVisit.is_voided.is_(False),
        )
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
    pricing = opd_settings_service.get_pricing(db)
    return {
        "admission": _admission_out(db, admission),
        "doctor_visits": [
            _visit_out(db, v, admission=admission, pricing=pricing) for v in visits
        ],
        "bills": [_bill_out(db, b) for b in bills],
        "running_bill": preview.model_dump(),
        "care_team": list_care_team(db, admission.id),
    }


def _care_team_member_out(db: Session, row: IpdAdmissionCareTeam) -> IpdCareTeamMemberOut:
    dept = (
        db.query(Department).filter(Department.id == row.department_id).first()
        if row.department_id
        else None
    )
    return IpdCareTeamMemberOut(
        id=row.id,
        admission_id=row.admission_id,
        doctor_id=row.doctor_id,
        doctor_name=h.doctor_display(db, row.doctor_id),
        department_id=row.department_id,
        department_name=dept.name if dept else None,
        role="associated",
        created_at=_iso(row.created_at),
    )


def list_care_team(db: Session, admission_id: int) -> list[dict]:
    rows = (
        db.query(IpdAdmissionCareTeam)
        .filter(IpdAdmissionCareTeam.admission_id == admission_id)
        .order_by(IpdAdmissionCareTeam.id.asc())
        .all()
    )
    return [_care_team_member_out(db, row).model_dump() for row in rows]


def add_care_team_doctor(
    db: Session,
    admission_id: int,
    data: IpdCareTeamAddRequest,
    *,
    added_by: Optional[int] = None,
) -> dict:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot update care team for a closed admission",
        )

    oh.get_doctor_in_department(db, data.doctor_id, data.department_id)

    if admission.doctor_id and int(admission.doctor_id) == int(data.doctor_id):
        raise HTTPException(
            status_code=400,
            detail="Doctor is already the primary doctor for this admission",
        )

    existing = (
        db.query(IpdAdmissionCareTeam)
        .filter(
            IpdAdmissionCareTeam.admission_id == admission.id,
            IpdAdmissionCareTeam.doctor_id == data.doctor_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Doctor is already on this admission care team",
        )

    row = IpdAdmissionCareTeam(
        admission_id=admission.id,
        doctor_id=data.doctor_id,
        department_id=data.department_id,
        added_by=added_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    notify_doctors_ipd_care_team_added(
        db, admission, associated_doctor_id=data.doctor_id, created_by=added_by
    )
    return _care_team_member_out(db, row).model_dump()


def remove_care_team_doctor(
    db: Session,
    admission_id: int,
    doctor_id: int,
    *,
    removed_by: Optional[int] = None,
) -> dict:
    admission = h.get_admission(db, admission_id)
    if admission.status != "admitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot update care team for a closed admission",
        )
    row = (
        db.query(IpdAdmissionCareTeam)
        .filter(
            IpdAdmissionCareTeam.admission_id == admission.id,
            IpdAdmissionCareTeam.doctor_id == doctor_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Care team doctor not found")
    db.delete(row)
    db.commit()
    notify_doctors_ipd_care_team_removed(
        db, admission, associated_doctor_id=doctor_id, created_by=removed_by
    )
    return {
        "message": "Doctor removed from care team",
        "admission_id": admission.id,
        "doctor_id": doctor_id,
    }


def doctor_has_admission_access(
    db: Session, admission: IpdAdmission, doctor_id: int
) -> bool:
    if admission.doctor_id and int(admission.doctor_id) == int(doctor_id):
        return True
    linked = (
        db.query(IpdAdmissionCareTeam.id)
        .filter(
            IpdAdmissionCareTeam.admission_id == admission.id,
            IpdAdmissionCareTeam.doctor_id == doctor_id,
        )
        .first()
    )
    return linked is not None


def _visit_out(
    db: Session,
    visit: IpdDoctorVisit,
    *,
    admission: Optional[IpdAdmission] = None,
    pricing=None,
) -> IpdDoctorVisitOut:
    """Charge is the amount billed for this visit, not only the saved snapshot."""
    from Services.ipd_doctor_visit_billing import billable_doctor_visit_amount

    admission = admission or h.get_admission(db, visit.admission_id)
    charge = billable_doctor_visit_amount(
        db,
        admission=admission,
        doctor_id=visit.doctor_id,
        stored_charge=visit.charge,
        pricing=pricing,
    )
    return IpdDoctorVisitOut(
        id=visit.id,
        admission_id=visit.admission_id,
        doctor_id=visit.doctor_id,
        doctor_name=h.doctor_display(db, visit.doctor_id),
        visited_at=_iso(visit.visited_at),
        charge=charge,
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
    return _visit_out(db, visit, admission=admission, pricing=pricing)


def _bed_days_for_admission(admission: IpdAdmission) -> int:
    """Open stays run to now. A discharged stay stops at discharged_at."""
    ended_at = None
    if (admission.status or "") == "discharged" and admission.discharged_at:
        ended_at = admission.discharged_at
    return opd_settings_service.calculate_bed_days(admission.admitted_at, ended_at)


def _charge_lines_for_admission(db: Session, admission: IpdAdmission) -> tuple[list[dict], float, int]:
    pricing = opd_settings_service.get_pricing(db)
    days = _bed_days_for_admission(admission)
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
        .filter(
            IpdDoctorVisit.admission_id == admission.id,
            IpdDoctorVisit.is_voided.is_(False),
        )
        .order_by(IpdDoctorVisit.visited_at.asc())
        .all()
    )
    from Services.ipd_doctor_visit_billing import billable_doctor_visit_amount

    for v in visits:
        doc = h.doctor_display(db, v.doctor_id) or "Doctor"
        amount = billable_doctor_visit_amount(
            db,
            admission=admission,
            doctor_id=v.doctor_id,
            stored_charge=v.charge,
            pricing=pricing,
        )
        items.append(
            {
                "description": f"Doctor Visit — {doc}",
                "qty": 1,
                "unit_price": amount,
                "amount": amount,
                "item_type": "visit",
            }
        )

    care_team = (
        db.query(IpdAdmissionCareTeam)
        .filter(IpdAdmissionCareTeam.admission_id == admission.id)
        .order_by(IpdAdmissionCareTeam.id.asc())
        .all()
    )
    for member in care_team:
        amount = round(
            float(
                opd_settings_service.resolve_consultation_fee(
                    pricing,
                    doctor_id=member.doctor_id,
                    department_id=member.department_id or admission.department_id,
                )
                or 0
            ),
            2,
        )
        if amount <= 0:
            continue
        doc = h.doctor_display(db, member.doctor_id) or "Doctor"
        items.append(
            {
                "description": f"Care Team — {doc}",
                "qty": 1,
                "unit_price": amount,
                "amount": amount,
                "item_type": "doctor",
            }
        )

    # Pharmacy dispensings linked via IPD prescriptions
    try:
        from Models.doctor_prescriptions import Prescription
        from Models.pharmacy_dispensing import Dispensing, DispensingItem

        pharmacy_rows = (
            db.query(DispensingItem, Dispensing)
            .join(Dispensing, Dispensing.id == DispensingItem.dispensing_id)
            .join(Prescription, Prescription.id == Dispensing.prescription_id)
            .filter(Prescription.admission_id == admission.id)
            .all()
        )
        from Services.ipd_billing_service import dispensed_medicine_amount

        for item, _disp in pharmacy_rows:
            amount = dispensed_medicine_amount(item.amount)
            qty = max(int(item.quantity_dispensed or 1), 1)
            unit = float(item.unit_price or 0) if item.unit_price is not None else (
                round(amount / qty, 2) if qty and amount else 0.0
            )
            items.append(
                {
                    "description": f"Pharmacy — {item.medicine_name or 'Medicine'}",
                    "qty": qty,
                    "unit_price": unit,
                    "amount": amount,
                    "item_type": "pharmacy",
                }
            )
    except Exception:
        db.rollback()

    lab_orders = (
        db.query(LabTestOrder)
        .filter(
            LabTestOrder.admission_id == admission.id,
            LabTestOrder.status == LabTestStatus.COMPLETED,
        )
        .order_by(LabTestOrder.updated_at.asc(), LabTestOrder.id.asc())
        .all()
    )
    from Services.ipd_billing_service import completed_lab_amount

    for order in lab_orders:
        amount = completed_lab_amount(order.price)
        items.append(
            {
                "description": f"Laboratory — {order.test_name or 'Test'}",
                "qty": 1,
                "unit_price": amount,
                "amount": amount,
                "item_type": "laboratory",
            }
        )

    # Saved Daily Charges are manual lines. Bed, visits, care team, pharmacy, and labs are already above.
    billing = (
        db.query(IpdAdmissionBilling)
        .filter(IpdAdmissionBilling.admission_id == admission.id)
        .first()
    )
    for row in (billing.daily_charges or []) if billing else []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip().lower()
        row_id = str(row.get("id") or "")
        if row.get("is_auto") is True or row.get("isAuto") is True:
            continue
        if row_id.startswith("auto-") or (source and source != "manual"):
            continue
        amount = round(float(row.get("amount") or 0), 2)
        if amount == 0:
            continue
        items.append(
            {
                "description": row.get("item_name") or row.get("head") or "Daily charge",
                "qty": 1,
                "unit_price": amount,
                "amount": amount,
                "item_type": "daily",
            }
        )

    subtotal = round(sum(i["amount"] for i in items), 2)
    return items, subtotal, days


def _finalized_bills(db: Session, admission_id: int) -> list[IpdBill]:
    """Final invoices only. Void and draft bills are not a pricing snapshot."""
    return (
        db.query(IpdBill)
        .options(selectinload(IpdBill.items))
        .filter(
            IpdBill.admission_id == admission_id,
            IpdBill.status == "final",
        )
        .order_by(IpdBill.id.asc())
        .all()
    )


def _preview_from_saved_bills(
    db: Session,
    admission: IpdAdmission,
    bills: list[IpdBill],
) -> IpdBillPreviewOut:
    """Closed stay: use the tax and totals saved on the invoice.

    Insurance-share lines on a cashless invoice are added back, so the stay
    still shows the full hospital bill.
    """
    subtotal = round(sum(float(b.subtotal or 0) for b in bills), 2)
    gst_amount = round(sum(float(b.gst_amount or 0) for b in bills), 2)
    grand = round(sum(float(b.grand_total or 0) for b in bills), 2)
    for bill in bills:
        less = round(
            -sum(
                float(item.amount or 0)
                for item in (bill.items or [])
                if item.item_type == INSURANCE_SHARE_ITEM_TYPE
            ),
            2,
        )
        if less <= 0.01:
            continue
        less_gst = round(less * float(bill.gst_percent or 0) / 100.0, 2)
        subtotal = round(subtotal + less, 2)
        gst_amount = round(gst_amount + less_gst, 2)
        grand = round(grand + less + less_gst, 2)
    rates = {round(float(b.gst_percent or 0), 2) for b in bills}
    gst_percent = rates.pop() if len(rates) == 1 else (
        round(gst_amount / subtotal * 100, 2) if subtotal else 0.0
    )
    items = [
        IpdBillItemOut(
            id=item.id,
            description=item.description,
            qty=item.qty,
            unit_price=float(item.unit_price),
            amount=float(item.amount),
            item_type=item.item_type,
        )
        for bill in bills
        for item in (bill.items or [])
        if item.item_type != INSURANCE_SHARE_ITEM_TYPE
    ]
    patient = db.query(Patient).filter(Patient.id == admission.patient_id).first()
    return IpdBillPreviewOut(
        admission_id=admission.id,
        admission_no=admission.admission_no,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else None,
        ward_name=admission.ward_name,
        bed_number=admission.bed_number,
        length_of_stay_days=_bed_days_for_admission(admission),
        bed_rate=float(items[0].unit_price) if items else 0.0,
        items=items,
        subtotal=subtotal,
        gst_percent=gst_percent,
        gst_amount=gst_amount,
        grand_total=grand,
    )


def _preview_charge_items(
    service_items: list[dict],
    line_subtotal: float,
    head_items: list[dict],
    head_net: float,
) -> tuple[list[dict], float]:
    """Pick the line list that adds up to the bill subtotal.

    Saved heads that change the total replace the service lines, so a Room
    head and the bed line are not both billed. Matching totals keep the
    service lines.
    """
    if head_items and abs(head_net - line_subtotal) > 0.01:
        return head_items, head_net
    if head_net > 0:
        return service_items, head_net
    return service_items, line_subtotal


def build_bill_preview(db: Session, admission_id: int) -> IpdBillPreviewOut:
    admission = h.get_admission(db, admission_id)
    saved = _finalized_bills(db, admission.id)
    if (admission.status or "") == "discharged" and admission.discharged_at and saved:
        return _preview_from_saved_bills(db, admission, saved)

    service_items, line_subtotal, days = _charge_lines_for_admission(db, admission)
    pricing = opd_settings_service.get_pricing(db)
    gst_percent = float(getattr(pricing, "gst_percent", None) or 0)
    _, line_gst, _line_grand = oh.bill_totals_from_subtotal(line_subtotal, gst_percent)
    # One breakdown for the table and the total. When a saved head changes
    # the money, the lines are those heads (Room replaces the bed line,
    # Treatment is included once). When they already match, keep the
    # visit, lab, and medicine lines.
    head_items, head_net = _saved_charge_head_invoice_items(db, admission)
    items, subtotal = _preview_charge_items(
        service_items, line_subtotal, head_items, head_net
    )
    if gst_percent > 0:
        gst_amount = round(subtotal * gst_percent / 100.0, 2)
    else:
        gst_amount = line_gst
    grand = round(subtotal + gst_amount, 2)
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


INSURANCE_SHARE_ITEM_TYPE = "insurance"


def _cashless_insurance_share(db: Session, admission: IpdAdmission) -> tuple[float, float]:
    """(Insurance cover, patient payments on the claim) for a cashless stay.

    Cover is the approved amount, else the estimate, else the claimed amount.
    Other stays return (0, 0).
    """
    from Services.ipd_insurance_split import coverage_limit

    claim = (
        db.query(IpdInsuranceClaim)
        .filter(IpdInsuranceClaim.admission_id == admission.id)
        .first()
    )
    if not claim or claim.claim_type != "cashless":
        return 0.0, 0.0
    cover, _source = coverage_limit(
        claim.approved_amount, claim.estimate_amount, claim.claimed_amount
    )
    claim_paid = sum(
        float(p.get("amount") or 0)
        for p in (claim.patient_payments or [])
        if isinstance(p, dict)
    )
    return round(cover, 2), round(max(claim_paid, 0.0), 2)


def _less_insurance_share_lines(
    items: list[dict],
    subtotal: float,
    gst_percent: float,
    target_grand: float,
    cover: float,
    claim_paid: float,
) -> tuple[list[dict], float, float, float]:
    """Cut an invoice down to the patient's share with negative lines.

    Returns (items, subtotal, gst_amount, grand_total); the lines add up to
    the new subtotal.
    """
    grand = round(target_grand, 2)
    if gst_percent > 0:
        new_subtotal = round(grand / (1 + gst_percent / 100.0), 2)
        gst_amount = round(grand - new_subtotal, 2)
    else:
        new_subtotal = grand
        gst_amount = 0.0
    less = round(new_subtotal - subtotal, 2)
    share = cover + claim_paid
    cover_part = round(less * cover / share, 2) if share > 0 else less
    paid_part = round(less - cover_part, 2)
    lines = list(items)
    for description, amount in (
        ("Less: insurance cover", cover_part),
        ("Less: paid on insurance claim", paid_part),
    ):
        if abs(amount) >= 0.01:
            lines.append(
                {
                    "description": description,
                    "qty": 1,
                    "unit_price": amount,
                    "amount": amount,
                    "item_type": INSURANCE_SHARE_ITEM_TYPE,
                }
            )
    return lines, new_subtotal, gst_amount, grand


def _saved_charge_head_invoice_items(
    db: Session, admission: IpdAdmission
) -> tuple[list[dict], float]:
    """Saved hospital charge heads as invoice lines. Empty when none were saved."""
    from Services import ipd_billing_service as billing

    row = (
        db.query(IpdAdmissionBilling)
        .filter(IpdAdmissionBilling.admission_id == admission.id)
        .first()
    )
    stored_heads = list(row.charge_heads or []) if row else []
    if not stored_heads:
        return [], 0.0

    stored_daily = list(row.daily_charges or []) if row else []
    transactions = billing.merge_daily_transactions(
        billing.build_auto_transactions(db, admission),
        stored_daily,
        admission,
    )
    items: list[dict] = []
    for head in billing.rollup_charge_heads(transactions, stored_heads):
        amount = round(float(head.get("amount") or 0), 2)
        if abs(amount) < 0.01:
            continue
        is_discount = (
            head.get("charge_category") == "discount" or head.get("id") == "discount"
        )
        signed = -abs(amount) if is_discount else amount
        items.append(
            {
                "description": head.get("label") or "Charge",
                "qty": 1,
                "unit_price": signed,
                "amount": signed,
                "item_type": head.get("charge_category") or "misc",
            }
        )
    return items, _charge_head_net(db, admission)


_INVOICE_CATEGORY = {
    "bed": "room",
    "room": "room",
    "visit": "doctor",
    "doctor": "doctor",
    "laboratory": "laboratory",
    "lab": "laboratory",
    "pharmacy": "pharmacy",
    "discount": "discount",
}


def _invoice_category(item_type: str | None) -> str:
    key = str(item_type or "misc").strip().lower()
    return _INVOICE_CATEGORY.get(key, key)


def _billed_category_totals(db: Session, admission_id: int) -> dict[str, float]:
    """Amounts already stored on earlier invoices, grouped by charge category."""
    bill_ids = [bill.id for bill in _non_void_bills(db, admission_id)]
    totals: dict[str, float] = {}
    if not bill_ids:
        return totals
    rows = db.query(IpdBillItem).filter(IpdBillItem.bill_id.in_(bill_ids)).all()
    for row in rows:
        category = _invoice_category(row.item_type)
        totals[category] = round(totals.get(category, 0.0) + float(row.amount or 0), 2)
    return totals


def _remainder_invoice_line(item: dict, remain: float) -> dict:
    unit = float(item.get("unit_price") or 0)
    qty = 1
    if abs(unit) > 0.009:
        scaled = remain / unit
        rounded = round(scaled)
        if abs(scaled - rounded) < 0.02 and rounded >= 1:
            qty = int(rounded)
            unit_price = unit
        else:
            unit_price = remain
    else:
        unit_price = remain
    return {
        "description": item.get("description") or "Charge",
        "qty": qty,
        "unit_price": round(unit_price, 2),
        "amount": round(remain, 2),
        "item_type": item.get("item_type") or "misc",
    }


def _unbilled_invoice_lines(items: list[dict], billed: dict[str, float]) -> list[dict]:
    """Drop amounts already invoiced. `billed` is reduced as lines are consumed."""
    lines: list[dict] = []
    for item in items:
        amount = round(float(item.get("amount") or 0), 2)
        if abs(amount) < 0.01:
            continue
        category = _invoice_category(item.get("item_type"))
        already = float(billed.get(category, 0.0))
        if amount > 0:
            used = min(max(already, 0.0), amount)
        else:
            used = max(min(already, 0.0), amount)
        billed[category] = round(already - used, 2)
        remain = round(amount - used, 2)
        if abs(remain) < 0.01:
            continue
        lines.append(_remainder_invoice_line(item, remain))
    return lines


def _lines_match_subtotal(lines: list[dict], target: float) -> bool:
    total = round(sum(float(line["amount"]) for line in lines), 2)
    return abs(total - round(target, 2)) <= 0.01


def _attach_new_zero_lines(
    lines: list[dict],
    detailed_items: list[dict],
    invoiced_counts: dict[str, int],
    *,
    item_type: str,
    fallback: str,
) -> list[dict]:
    """Keep a zero-price line on a later invoice without changing the amount due."""
    remaining = dict(invoiced_counts)
    attached = list(lines)
    for item in detailed_items:
        if str(item.get("item_type") or "") != item_type:
            continue
        if abs(round(float(item.get("amount") or 0), 2)) >= 0.01:
            continue
        description = str(item.get("description") or fallback)
        already = int(remaining.get(description) or 0)
        if already > 0:
            remaining[description] = already - 1
            continue
        try:
            qty = int(item.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1
        attached.append(
            {
                "description": description,
                "qty": qty if qty >= 1 else 1,
                "unit_price": 0.0,
                "amount": 0.0,
                "item_type": item_type,
            }
        )
    return attached


def _attach_new_zero_visits(
    lines: list[dict],
    detailed_items: list[dict],
    invoiced_zero_visits: dict[str, int],
) -> list[dict]:
    """Keep a free consultation on a later invoice without changing the amount due."""
    return _attach_new_zero_lines(
        lines,
        detailed_items,
        invoiced_zero_visits,
        item_type="visit",
        fallback="Doctor Visit",
    )


def _attach_new_zero_labs(
    lines: list[dict],
    detailed_items: list[dict],
    invoiced_zero_labs: dict[str, int],
) -> list[dict]:
    """Keep a completed zero-price lab on a later invoice without changing the amount due."""
    return _attach_new_zero_lines(
        lines,
        detailed_items,
        invoiced_zero_labs,
        item_type="laboratory",
        fallback="Laboratory — Test",
    )


def _invoiced_zero_line_counts(
    db: Session, admission_id: int, item_type: str, fallback: str
) -> dict[str, int]:
    bill_ids = [bill.id for bill in _non_void_bills(db, admission_id)]
    counts: dict[str, int] = {}
    if not bill_ids:
        return counts
    rows = (
        db.query(IpdBillItem)
        .filter(
            IpdBillItem.bill_id.in_(bill_ids),
            IpdBillItem.item_type == item_type,
        )
        .all()
    )
    for row in rows:
        if abs(float(row.amount or 0)) >= 0.01:
            continue
        description = str(row.description or fallback)
        counts[description] = counts.get(description, 0) + 1
    return counts


def _invoiced_zero_visit_counts(db: Session, admission_id: int) -> dict[str, int]:
    return _invoiced_zero_line_counts(db, admission_id, "visit", "Doctor Visit")


def _invoiced_zero_lab_counts(db: Session, admission_id: int) -> dict[str, int]:
    return _invoiced_zero_line_counts(db, admission_id, "laboratory", "Laboratory — Test")


def _attach_new_zero_pharmacy(
    lines: list[dict],
    detailed_items: list[dict],
    invoiced_zero_pharmacy: dict[str, int],
) -> list[dict]:
    """Keep a dispensed medicine with amount 0 on a later invoice."""
    return _attach_new_zero_lines(
        lines,
        detailed_items,
        invoiced_zero_pharmacy,
        item_type="pharmacy",
        fallback="Pharmacy — Medicine",
    )


def _invoiced_zero_pharmacy_counts(db: Session, admission_id: int) -> dict[str, int]:
    return _invoiced_zero_line_counts(db, admission_id, "pharmacy", "Pharmacy — Medicine")


def _follow_up_invoice_lines(
    detailed_items: list[dict],
    current_items: list[dict],
    billed: dict[str, float],
    target: float,
    invoiced_zero_visits: dict[str, int] | None = None,
    invoiced_zero_labs: dict[str, int] | None = None,
    invoiced_zero_pharmacy: dict[str, int] | None = None,
) -> list[dict]:
    """Itemize only the unpaid remainder. Lines must add up to this invoice's subtotal."""
    service_categories = {"room", "doctor", "laboratory", "pharmacy", "discount"}
    detailed_delta = _unbilled_invoice_lines(detailed_items, dict(billed))
    current_delta = _unbilled_invoice_lines(current_items, dict(billed))

    pool = dict(billed)
    combined = _unbilled_invoice_lines(detailed_items, pool)
    seen = {
        (line["description"], line.get("item_type"), round(float(line["amount"]), 2))
        for line in combined
    }
    extras = [
        item
        for item in current_items
        if _invoice_category(item.get("item_type")) not in service_categories
    ]
    for line in _unbilled_invoice_lines(extras, pool):
        key = (line["description"], line.get("item_type"), round(float(line["amount"]), 2))
        if key in seen:
            continue
        combined.append(line)
        seen.add(key)

    zero_visits = invoiced_zero_visits or {}
    zero_labs = invoiced_zero_labs or {}
    zero_pharmacy = invoiced_zero_pharmacy or {}

    def _finish(chosen: list[dict]) -> list[dict]:
        with_visits = _attach_new_zero_visits(chosen, detailed_items, zero_visits)
        with_labs = _attach_new_zero_labs(with_visits, detailed_items, zero_labs)
        return _attach_new_zero_pharmacy(with_labs, detailed_items, zero_pharmacy)

    for candidate in (combined, detailed_delta, current_delta):
        if candidate and _lines_match_subtotal(candidate, target):
            return _finish(candidate)

    partial = detailed_delta or current_delta
    covered = round(sum(float(line["amount"]) for line in partial), 2) if partial else 0.0
    gap = round(target - covered, 2)
    if partial and covered > 0.01 and gap > 0.01:
        return _finish(
            partial
            + [
                {
                    "description": "Additional IPD charges",
                    "qty": 1,
                    "unit_price": gap,
                    "amount": gap,
                    "item_type": "misc",
                }
            ]
        )
    return _finish(
        [
            {
                "description": "Additional IPD charges",
                "qty": 1,
                "unit_price": target,
                "amount": target,
                "item_type": "misc",
            }
        ]
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

    detailed_items, line_subtotal, _days = _charge_lines_for_admission(db, admission)
    head_items, head_net = _saved_charge_head_invoice_items(db, admission)
    # Saved procedure/package heads are not in the bed/visit/pharmacy lines.
    # Invoice those heads so the bill matches the charge-head total.
    if head_items and abs(head_net - line_subtotal) > 0.01:
        preview_items = [dict(item) for item in head_items]
        subtotal = head_net
    else:
        preview_items = [dict(item) for item in detailed_items]
        subtotal = line_subtotal
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

    cover, claim_paid = _cashless_insurance_share(db, admission)
    insurance_share = round(cover + claim_paid, 2)
    already_billed = _already_billed_total(db, admission.id)
    due_to_bill = round(max(grand - insurance_share - already_billed, 0), 2)
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
        preview_items = _follow_up_invoice_lines(
            detailed_items,
            preview_items,
            _billed_category_totals(db, admission.id),
            subtotal,
            _invoiced_zero_visit_counts(db, admission.id),
            _invoiced_zero_lab_counts(db, admission.id),
            _invoiced_zero_pharmacy_counts(db, admission.id),
        )
    elif insurance_share > 0.01:
        preview_items, subtotal, gst_amount, grand = _less_insurance_share_lines(
            preview_items, subtotal, gst_percent, due_to_bill, cover, claim_paid
        )

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


def _sync_open_bill_to_live_charges(db: Session, bill: IpdBill) -> None:
    """Grow an open invoice to cover charges added after it was generated.

    Paid amounts are kept. The total never goes down, so money already
    collected on this invoice is never more than its total.
    """
    if bill.status == "void" or (bill.payment_status or "") not in ("pending", "partial"):
        return
    admission = h.get_admission(db, bill.admission_id)
    if admission.status in ("cancelled", "discharged"):
        return

    preview = build_bill_preview(db, admission.id)
    other_billed = round(
        sum(
            float(b.grand_total or 0)
            for b in _non_void_bills(db, admission.id)
            if b.id != bill.id
        ),
        2,
    )
    cover, claim_paid = _cashless_insurance_share(db, admission)
    insurance_share = round(cover + claim_paid, 2)
    target = round(
        float(preview.grand_total or 0) - insurance_share - other_billed, 2
    )
    if target <= float(bill.grand_total or 0) + 0.01:
        return

    gst_percent = float(preview.gst_percent or 0)
    if gst_percent > 0:
        subtotal = round(target / (1 + gst_percent / 100.0), 2)
        gst_amount = round(target - subtotal, 2)
    else:
        subtotal = target
        gst_amount = 0.0

    detailed_items, _line_subtotal, _days = _charge_lines_for_admission(db, admission)
    preview_items = [item.model_dump(exclude={"id"}) for item in preview.items]

    db.query(IpdBillItem).filter(IpdBillItem.bill_id == bill.id).delete(
        synchronize_session=False
    )
    db.flush()

    if other_billed > 0.01:
        lines = _follow_up_invoice_lines(
            detailed_items,
            preview_items,
            _billed_category_totals(db, admission.id),
            subtotal,
            _invoiced_zero_visit_counts(db, admission.id),
            _invoiced_zero_lab_counts(db, admission.id),
            _invoiced_zero_pharmacy_counts(db, admission.id),
        )
    elif insurance_share > 0.01:
        lines, subtotal, gst_amount, _grand = _less_insurance_share_lines(
            preview_items,
            float(preview.subtotal or 0),
            gst_percent,
            target,
            cover,
            claim_paid,
        )
    else:
        lines = preview_items

    for item in lines:
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

    paid = round(float(bill.paid_amount or 0), 2)
    bill.subtotal = subtotal
    bill.gst_percent = gst_percent
    bill.gst_amount = gst_amount
    bill.grand_total = target
    bill.balance_due = round(max(target - paid, 0), 2)
    bill.payment_status = "partial" if paid > 0 else "pending"
    db.flush()
    db.expire(bill, ["items"])


def collect_payment(
    db: Session, bill_id: int, data: IpdCollectPaymentRequest, recorded_by: int
) -> IpdBillOut:
    bill = db.query(IpdBill).filter(IpdBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="IPD bill not found")
    if bill.status == "void":
        raise HTTPException(status_code=400, detail="Cannot pay a void bill")
    _sync_open_bill_to_live_charges(db, bill)
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


def _charge_head_net(db: Session, admission: IpdAdmission) -> float:
    """Charge-head total used by the opened bill, including saved daily charges."""
    from Services import ipd_billing_service as billing

    row = (
        db.query(IpdAdmissionBilling)
        .filter(IpdAdmissionBilling.admission_id == admission.id)
        .first()
    )
    stored_daily = list(row.daily_charges or []) if row else []
    stored_heads = list(row.charge_heads or []) if row else []
    transactions = billing.merge_daily_transactions(
        billing.build_auto_transactions(db, admission),
        stored_daily,
        admission,
    )
    gross = 0.0
    discount = 0.0
    for head in billing.rollup_charge_heads(transactions, stored_heads):
        amount = round(float(head.get("amount") or 0), 2)
        if head.get("charge_category") == "discount" or head.get("id") == "discount":
            discount += amount
        else:
            gross += amount
    return round(max(0.0, gross - discount), 2)


def _detail_running_total(db: Session, admission: IpdAdmission, preview: IpdBillPreviewOut) -> float:
    """Match the bill detail Total: charge-head net, then the same GST."""
    net = _charge_head_net(db, admission)
    subtotal = net if net > 0 else float(preview.subtotal or 0)
    gst_percent = float(preview.gst_percent or 0)
    if gst_percent > 0:
        gst_amount = round(subtotal * gst_percent / 100, 2)
    else:
        gst_amount = float(preview.gst_amount or 0)
    return round(subtotal + gst_amount, 2)


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
        running_total = _detail_running_total(db, adm, preview)
        # Paid stays the cash recorded on invoices, including when that cash
        # is higher than today's live total. Due is whatever is still unpaid.
        paid_balance = round(max(_paid_towards_admission(db, adm.id), 0), 2)
        due_balance = round(max(running_total - paid_balance, 0), 2)
        if due_balance <= 0.01:
            due_balance = 0.0
        open_bill_id = unpaid.id if unpaid else None

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
        "hospital": hospital_settings_service.letterhead_for_tenant(db, admission.tenant_id),
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
    if search and search.strip():
        q = q.filter(
            admission_text_search_filter(
                search,
                IpdBill.bill_number,
                IpdPaymentTransaction.transaction_reference,
            )
        )

    entries: list[dict] = []
    for txn, bill, adm, patient in q.all():
        entries.append(
            {
                "id": txn.id,
                "sort_at": txn.paid_at,
                "paid_at": _iso(txn.paid_at),
                "receipt_no": f"IPD-RCPT-{txn.id:05d}",
                "amount": float(txn.amount or 0),
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
    entries.extend(_claim_payment_entries(db, search))
    entries.sort(key=lambda row: _payment_sort_key(row["sort_at"]), reverse=True)
    coverage = _insurance_coverage_entries(db, search)
    coverage.sort(key=lambda row: _payment_sort_key(row["sort_at"]), reverse=True)

    # Money actually received. Insurance coverage is not collected money, so
    # it stays out of the total and only feeds the Insurance card.
    by_mode: dict[str, float] = {"cash": 0.0, "upi": 0.0, "card": 0.0, "insurance": 0.0}
    total_collected = 0.0
    for row in entries:
        total_collected += row["amount"]
        by_mode[row["mode"]] = by_mode.get(row["mode"], 0.0) + row["amount"]
    insurance_covered = round(sum(row["amount"] for row in coverage), 2)

    filtered = entries
    if payment_mode:
        want = _norm_payment_mode(payment_mode)
        if want == "insurance":
            filtered = coverage
        else:
            filtered = [row for row in entries if row["mode"] == want]

    page_rows = filtered[(page - 1) * limit : page * limit]
    items = [{k: v for k, v in row.items() if k != "sort_at"} for row in page_rows]
    return {
        "summary": {
            "total_collected": round(total_collected, 2),
            "cash": round(by_mode.get("cash", 0), 2),
            "upi": round(by_mode.get("upi", 0), 2),
            "card": round(by_mode.get("card", 0), 2),
            "insurance": insurance_covered,
            "insurance_covered": insurance_covered,
            "insurance_received": round(by_mode.get("insurance", 0), 2),
            "transaction_count": len(entries),
        },
        "total": len(filtered),
        "page": page,
        "limit": limit,
        "items": items,
    }


def _payment_sort_key(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return value


def _claim_payment_paid_at(raw: Optional[str], fallback: Optional[datetime]) -> Optional[datetime]:
    if raw:
        try:
            return _parse_dt(str(raw))
        except HTTPException:
            pass
    return fallback


def _claim_payment_entries(db: Session, search: Optional[str]) -> list[dict]:
    """Insurer and patient payments saved on insurance claims, not on invoices."""
    q = (
        db.query(IpdInsuranceClaim, IpdAdmission, Patient)
        .join(IpdAdmission, IpdInsuranceClaim.admission_id == IpdAdmission.id)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
    )
    if search and search.strip():
        q = q.filter(admission_text_search_filter(search))

    rows: list[dict] = []
    for claim, adm, patient in q.all():
        sources = (
            ("insurance", claim.insurance_payments or []),
            ("patient", claim.patient_payments or []),
        )
        for kind, payments in sources:
            for index, payment in enumerate(payments):
                if not isinstance(payment, dict):
                    continue
                try:
                    amount = round(float(payment.get("amount") or 0), 2)
                except (TypeError, ValueError):
                    continue
                if amount <= 0:
                    continue
                if kind == "insurance":
                    mode = "insurance"
                else:
                    mode = _norm_payment_mode(payment.get("mode") or payment.get("paymentMode"))
                    if mode not in {"cash", "card", "upi", "insurance"}:
                        mode = "cash"
                paid_at = _claim_payment_paid_at(
                    payment.get("paid_at") or payment.get("paidAt"),
                    claim.updated_at,
                )
                rows.append(
                    {
                        "id": f"claim-{claim.id}-{kind}-{payment.get('id') or index}",
                        "sort_at": paid_at,
                        "paid_at": _iso(paid_at),
                        "receipt_no": f"IPD-CLM-{claim.id:05d}-{index + 1}",
                        "amount": amount,
                        "mode": mode,
                        "reference": payment.get("reference"),
                        "bill_id": None,
                        "bill_number": None,
                        "bill_balance": 0.0,
                        "admission_id": adm.id,
                        "admission_no": adm.admission_no,
                        "patient_name": h.display_name(patient.first_name, patient.last_name),
                        "patient_uid": patient.patient_uid,
                    }
                )
    return rows


def _insurance_coverage_entries(db: Session, search: Optional[str]) -> list[dict]:
    """One row per cashless stay: the part of the bill insurance covers.

    Coverage is not money received. Rows say whether it is an estimate
    (still admitted) or final (discharged), and how much the insurer paid.
    """
    from Services.ipd_insurance_split import coverage_status, insurance_split

    q = (
        db.query(IpdInsuranceClaim, IpdAdmission, Patient)
        .join(IpdAdmission, IpdInsuranceClaim.admission_id == IpdAdmission.id)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
        .filter(
            IpdInsuranceClaim.claim_type == "cashless",
            IpdAdmission.status.in_(("admitted", "discharged")),
        )
    )
    if search and search.strip():
        q = q.filter(admission_text_search_filter(search))

    rows: list[dict] = []
    for claim, adm, patient in q.all():
        preview = build_bill_preview(db, adm.id)
        split = insurance_split(
            preview.grand_total,
            approved=claim.approved_amount,
            estimate=claim.estimate_amount,
            claimed=claim.claimed_amount,
        )
        share = split["insurance_share"]
        if share <= 0.009:
            continue
        received = round(
            sum(
                float(p.get("amount") or 0)
                for p in (claim.insurance_payments or [])
                if isinstance(p, dict)
            ),
            2,
        )
        discharged = (adm.status or "") == "discharged"
        bills = _non_void_bills(db, adm.id)
        latest_bill = bills[-1] if bills else None
        sort_at = (adm.discharged_at if discharged else None) or adm.admitted_at
        rows.append(
            {
                "id": f"coverage-{claim.id}",
                "entry_type": "insurance_coverage",
                "sort_at": sort_at,
                "paid_at": _iso(sort_at),
                "receipt_no": f"IPD-COV-{claim.id:05d}",
                "amount": share,
                "mode": "insurance",
                "reference": None,
                "bill_id": latest_bill.id if latest_bill else None,
                "bill_number": latest_bill.bill_number if latest_bill else None,
                "bill_balance": 0.0,
                "admission_id": adm.id,
                "admission_no": adm.admission_no,
                "patient_name": h.display_name(patient.first_name, patient.last_name),
                "patient_uid": patient.patient_uid,
                "bill_total": split["bill_total"],
                "coverage_source": split["coverage_source"],
                "coverage_basis": "final" if discharged else "estimated",
                "coverage_status": coverage_status(share, received),
                "insurer_received": received,
                "insurer_pending": round(max(share - received, 0.0), 2),
            }
        )
    return rows


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

    # Close the stay and free the bed. Do not create a pay-later invoice.
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
        "bill": None,
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
