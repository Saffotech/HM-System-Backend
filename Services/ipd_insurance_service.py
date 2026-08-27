"""IPD insurance claims — create on admit, list/detail/update for FE screens."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.ipd import IpdAdmission, IpdInsuranceClaim
from Models.patient import Patient
from Schemas.ipd_schema import (
    IpdAdmitInsuranceIn,
    IpdInsuranceClaimUpdate,
    IpdInsurancePaymentIn,
)
from Services import ipd_helpers as h
from Services.doctor_helpers import format_patient_age_label, patient_age

IST = ZoneInfo("Asia/Kolkata")


def _now() -> datetime:
    return datetime.now(IST)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(IST).isoformat()


def coverage_label(claim_type: str) -> str:
    if claim_type == "cashless":
        return "Cashless Insurance"
    return "Copay"


def payment_type_from_claim_type(claim_type: str) -> str:
    if claim_type == "cashless":
        return "insurance_cashless"
    return "insurance_copay"


def resolve_admit_payment(
    payment_mode: Optional[str],
    self_pay_method: Optional[str],
    insurance: Optional[IpdAdmitInsuranceIn],
) -> tuple[str, Optional[str]]:
    """Returns (payment_type, self_pay_method)."""
    mode = (payment_mode or "self").strip().lower()
    if mode == "insurance":
        if not insurance:
            raise HTTPException(
                status_code=400,
                detail="insurance details are required when payment_mode is insurance",
            )
        return payment_type_from_claim_type(insurance.claim_type), None
    return "self", (self_pay_method or None)


def create_claim_for_admission(
    db: Session,
    *,
    admission: IpdAdmission,
    insurance: IpdAdmitInsuranceIn,
    created_by: Optional[int],
) -> IpdInsuranceClaim:
    claim = IpdInsuranceClaim(
        admission_id=admission.id,
        patient_id=admission.patient_id,
        claim_type=insurance.claim_type,
        insurer=insurance.insurer.strip(),
        policy_no=insurance.policy_no.strip(),
        policy_holder=insurance.policy_holder.strip(),
        relationship=insurance.relationship.strip(),
        member_id=(insurance.member_id or "").strip() or None,
        claimed_amount=float(insurance.claimed_amount or 0),
        estimate_amount=(
            float(insurance.estimate_amount)
            if insurance.estimate_amount is not None
            else None
        ),
        approved_amount=0.0,
        policy_status="Active",
        claim_status="pending",
        insurance_payments=[],
        patient_payments=[],
        created_by=created_by,
    )
    db.add(claim)

    patient = db.query(Patient).filter(Patient.id == admission.patient_id).first()
    if patient:
        patient.insurance_policy_no = claim.policy_no

    return claim


def _age_gender(patient: Optional[Patient]) -> str:
    if not patient:
        return "—"
    age_label = format_patient_age_label(patient.date_of_birth)
    if not age_label:
        years = patient_age(patient.date_of_birth)
        age_label = f"{years}y" if years is not None else "—"
    gender = (patient.gender or "").strip()
    if gender and age_label != "—":
        return f"{age_label} / {gender}"
    if gender:
        return gender
    return age_label


def _status_label(claim: IpdInsuranceClaim) -> str:
    status = (claim.claim_status or "pending").replace("_", " ")
    created = _iso(claim.created_at) or ""
    day = ""
    if claim.created_at:
        day = claim.created_at.astimezone(IST).strftime("%d %b %Y")
    return f"{status} · {day}".strip(" ·") if day else status


def _ward_room(admission: Optional[IpdAdmission]) -> str:
    if not admission:
        return "—"
    parts = [admission.ward_name, admission.bed_number]
    return " / ".join(p for p in parts if p) or "—"


def serialize_claim(
    db: Session,
    claim: IpdInsuranceClaim,
    *,
    admission: Optional[IpdAdmission] = None,
    patient: Optional[Patient] = None,
) -> dict[str, Any]:
    admission = admission or claim.admission
    if admission is None and claim.admission_id:
        admission = h.get_admission(db, claim.admission_id)
    patient = patient or (
        db.query(Patient).filter(Patient.id == claim.patient_id).first()
    )
    doctor_name = h.doctor_display(db, admission.doctor_id) if admission and admission.doctor_id else None
    if not doctor_name and admission:
        doctor_name = "—"

    net_bill = 0.0
    if admission:
        for bill in admission.bills or []:
            if bill.status != "void":
                net_bill = max(net_bill, float(bill.grand_total or 0))

    patient_paid = sum(
        float(p.get("amount") or 0) for p in (claim.patient_payments or [])
    )
    ins_paid = sum(
        float(p.get("amount") or 0) for p in (claim.insurance_payments or [])
    )
    approved = float(claim.approved_amount or 0)
    claimed = float(claim.claimed_amount or 0)
    patient_responsibility = max(claimed - approved, 0) if approved else None

    return {
        "id": claim.id,
        "claim_id": claim.id,
        "admission_id": claim.admission_id,
        "patient_id": claim.patient_id,
        "patient_uid": patient.patient_uid if patient else None,
        "uhid": patient.patient_uid if patient else None,
        "patient_name": (
            h.display_name(patient.first_name, patient.last_name) if patient else None
        ),
        "age_gender": _age_gender(patient),
        "phone": patient.phone if patient else None,
        "ipd_id": admission.admission_no if admission else None,
        "admission_no": admission.admission_no if admission else None,
        "admission_date": _iso(admission.admitted_at) if admission else None,
        "discharge_date": _iso(admission.discharged_at) if admission else "—",
        "doctor": doctor_name,
        "doctor_name": doctor_name,
        "ward_room": _ward_room(admission),
        "claim_type": claim.claim_type,
        "coverage": coverage_label(claim.claim_type),
        "coverage_type": claim.claim_type,
        "payment_type": payment_type_from_claim_type(claim.claim_type),
        "insurer": claim.insurer,
        "insurance_company": claim.insurer,
        "policy_no": claim.policy_no,
        "policyNo": claim.policy_no,
        "policy_holder": claim.policy_holder,
        "policyHolder": claim.policy_holder,
        "relationship": claim.relationship,
        "member_id": claim.member_id,
        "memberId": claim.member_id,
        "claimed": claimed,
        "claimed_amount": claimed,
        "claimedAmount": claimed,
        "estimate_amount": claim.estimate_amount,
        "estimateAmount": claim.estimate_amount,
        "approved": approved,
        "approved_amount": approved,
        "available_si": claim.available_si,
        "availableSi": claim.available_si,
        "policy_status": claim.policy_status,
        "policyStatus": claim.policy_status,
        "claim_status": claim.claim_status,
        "status_label": _status_label(claim),
        "claim_label": _status_label(claim),
        "net_bill": net_bill,
        "netBill": net_bill,
        "patient_responsibility": patient_responsibility,
        "patientResponsibility": patient_responsibility,
        "insurance_paid": ins_paid,
        "patient_paid": patient_paid,
        "charges": [],
        "daily_charges": [],
        "dailyCharges": [],
        "responsibility_lines": [],
        "responsibilityLines": [],
        "insurance_payments": claim.insurance_payments or [],
        "insurancePayments": claim.insurance_payments or [],
        "patient_payments": claim.patient_payments or [],
        "patientPayments": claim.patient_payments or [],
        "created_at": _iso(claim.created_at),
        "createdLabel": (
            claim.created_at.astimezone(IST).strftime("%d %b %Y")
            if claim.created_at
            else None
        ),
        "admitted": (
            admission.admitted_at.astimezone(IST).strftime("%d %b %Y")
            if admission and admission.admitted_at
            else None
        ),
    }


def serialize_patient_bundle(
    db: Session,
    claim: IpdInsuranceClaim,
) -> dict[str, Any]:
    admission = claim.admission or h.get_admission(db, claim.admission_id)
    patient = db.query(Patient).filter(Patient.id == claim.patient_id).first()
    claim_out = serialize_claim(db, claim, admission=admission, patient=patient)
    patient_out = {
        "id": patient.patient_uid if patient else str(claim.patient_id),
        "patient_id": claim.patient_id,
        "admission_id": claim.admission_id,
        "admissionId": claim.admission_id,
        "claim_id": claim.id,
        "claimId": claim.id,
        "patient_name": claim_out.get("patient_name"),
        "patientName": claim_out.get("patient_name"),
        "age_gender": claim_out.get("age_gender"),
        "ageGender": claim_out.get("age_gender"),
        "phone": claim_out.get("phone") or "—",
        "uhid": claim_out.get("uhid"),
        "coverage": claim_out.get("coverage"),
        "insurer": claim.insurer,
        "policy_no": claim.policy_no,
        "policyNo": claim.policy_no,
        "available_si": claim.available_si,
        "availableSi": claim.available_si,
        "policy_status": claim.policy_status,
        "policyStatus": claim.policy_status,
        "registered_on": claim_out.get("createdLabel"),
        "registeredOn": claim_out.get("createdLabel"),
        "payment_type": claim_out.get("payment_type"),
    }
    return {"patient": patient_out, "claim": claim_out}


def _claim_query(db: Session):
    return db.query(IpdInsuranceClaim).options(
        joinedload(IpdInsuranceClaim.admission).joinedload(IpdAdmission.bills),
    )


def get_claim_by_id(db: Session, claim_id: int) -> IpdInsuranceClaim:
    claim = _claim_query(db).filter(IpdInsuranceClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Insurance claim not found")
    return claim


def resolve_claim_id(raw: str | int) -> int:
    text = str(raw).strip()
    if text.startswith("pending-"):
        # Legacy FE nav id — resolve via admission id
        try:
            admission_id = int(text.split("-", 1)[1])
        except (IndexError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Insurance claim not found") from exc
        return admission_id  # caller must look up by admission when pending-
    try:
        return int(text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Insurance claim not found") from exc


def get_claim_flexible(db: Session, claim_key: str | int) -> IpdInsuranceClaim:
    text = str(claim_key).strip()
    if text.startswith("pending-"):
        try:
            admission_id = int(text.split("-", 1)[1])
        except (IndexError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Insurance claim not found") from exc
        claim = (
            _claim_query(db)
            .filter(IpdInsuranceClaim.admission_id == admission_id)
            .first()
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Insurance claim not found")
        return claim
    return get_claim_by_id(db, resolve_claim_id(text))


def get_latest_claim_for_patient_key(db: Session, patient_key: str) -> IpdInsuranceClaim:
    """patient_key = patient_uid (P-1027) or numeric patient id."""
    key = str(patient_key).strip()
    patient: Optional[Patient] = None
    if key.isdigit():
        patient = db.query(Patient).filter(Patient.id == int(key)).first()
    if not patient:
        patient = (
            db.query(Patient)
            .filter(Patient.patient_uid.ilike(key))
            .first()
        )
    if not patient:
        raise HTTPException(status_code=404, detail="Insurance patient not found")

    claim = (
        _claim_query(db)
        .filter(IpdInsuranceClaim.patient_id == patient.id)
        .join(IpdAdmission, IpdAdmission.id == IpdInsuranceClaim.admission_id)
        .order_by(IpdAdmission.admitted_at.desc(), IpdInsuranceClaim.id.desc())
        .first()
    )
    if not claim:
        raise HTTPException(
            status_code=404,
            detail="No insurance claim found for this patient",
        )
    return claim


def list_insurance_patients(
    db: Session,
    *,
    search: Optional[str] = None,
    claim_type: Optional[str] = None,
    status: Optional[str] = None,
    ward: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    page = max(page, 1)
    limit = min(max(limit, 1), 100)

    query = (
        db.query(IpdInsuranceClaim)
        .join(IpdAdmission, IpdAdmission.id == IpdInsuranceClaim.admission_id)
        .join(Patient, Patient.id == IpdInsuranceClaim.patient_id)
        .options(
            joinedload(IpdInsuranceClaim.admission).joinedload(IpdAdmission.bills),
        )
    )

    # Default list = cashless for insurance patients table
    if claim_type:
        ct = claim_type.strip().lower()
        if ct in {"cashless", "insurance_cashless"}:
            query = query.filter(IpdInsuranceClaim.claim_type == "cashless")
        elif ct in {"pay_and_claim", "copay", "insurance_copay"}:
            query = query.filter(IpdInsuranceClaim.claim_type == "pay_and_claim")
    else:
        query = query.filter(IpdInsuranceClaim.claim_type == "cashless")

    if status:
        query = query.filter(IpdAdmission.status == status)
    if ward:
        query = query.filter(IpdAdmission.ward_name.ilike(ward.strip()))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                Patient.phone.ilike(term),
                IpdInsuranceClaim.policy_no.ilike(term),
                IpdInsuranceClaim.insurer.ilike(term),
                IpdAdmission.admission_no.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(IpdAdmission.admitted_at.desc(), IpdInsuranceClaim.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = []
    for claim in rows:
        bundle = serialize_patient_bundle(db, claim)
        patient = bundle["patient"]
        items.append(
            {
                **patient,
                "id": patient["id"],
                "admissionId": patient["admissionId"],
                "claimId": patient["claimId"],
                "patientName": patient["patientName"],
                "uhid": patient["uhid"],
                "ageGender": patient["ageGender"],
                "coverage": patient["coverage"],
                "insurer": patient["insurer"],
                "policyNo": patient["policyNo"],
                "availableSi": patient["availableSi"],
                "policyStatus": patient["policyStatus"],
            }
        )

    return {"items": items, "total": total, "page": page, "limit": limit}


def list_insurance_bills(
    db: Session,
    *,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    query = (
        db.query(IpdInsuranceClaim)
        .join(IpdAdmission, IpdAdmission.id == IpdInsuranceClaim.admission_id)
        .join(Patient, Patient.id == IpdInsuranceClaim.patient_id)
        .options(
            joinedload(IpdInsuranceClaim.admission).joinedload(IpdAdmission.bills),
        )
        .filter(IpdInsuranceClaim.claim_type == "cashless")
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                IpdAdmission.admission_no.ilike(term),
            )
        )
    total = query.count()
    rows = (
        query.order_by(IpdAdmission.admitted_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = []
    for claim in rows:
        c = serialize_claim(db, claim)
        items.append(
            {
                "id": c["id"],
                "patient_id": c.get("uhid") or c["patient_id"],
                "patientId": c.get("uhid") or c["patient_id"],
                "ipd_id": c.get("ipd_id"),
                "ipdId": c.get("ipd_id"),
                "patient_name": c.get("patient_name"),
                "patientName": c.get("patient_name"),
                "uhid": c.get("uhid"),
                "age_gender": c.get("age_gender"),
                "ageGender": c.get("age_gender"),
                "admitted": c.get("admitted"),
                "doctor": c.get("doctor"),
                "ward_room": c.get("ward_room"),
                "wardRoom": c.get("ward_room"),
                "coverage": c.get("coverage"),
                "net_bill": c.get("net_bill"),
                "netBill": c.get("net_bill"),
                "approved": c.get("approved"),
                "claim_label": c.get("claim_label"),
                "claimLabel": c.get("claim_label"),
            }
        )
    return {"items": items, "total": total, "page": page, "limit": limit}


def update_claim(
    db: Session,
    claim: IpdInsuranceClaim,
    payload: IpdInsuranceClaimUpdate,
) -> IpdInsuranceClaim:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    if "claimed" in data and "claimed_amount" not in data:
        data["claimed_amount"] = data.pop("claimed")
    else:
        data.pop("claimed", None)

    field_map = {
        "insurer": "insurer",
        "policy_no": "policy_no",
        "policy_holder": "policy_holder",
        "relationship": "relationship",
        "member_id": "member_id",
        "claimed_amount": "claimed_amount",
        "estimate_amount": "estimate_amount",
        "policy_status": "policy_status",
        "claim_status": "claim_status",
        "approved_amount": "approved_amount",
        "available_si": "available_si",
    }
    for src, dest in field_map.items():
        if src in data and data[src] is not None:
            value = data[src]
            if isinstance(value, str):
                value = value.strip()
            setattr(claim, dest, value)

    claim.updated_at = _now()

    if claim.policy_no:
        patient = db.query(Patient).filter(Patient.id == claim.patient_id).first()
        if patient:
            patient.insurance_policy_no = claim.policy_no

    db.commit()
    db.refresh(claim)
    return claim


def update_patient_insurance(
    db: Session,
    patient_key: str,
    payload: IpdInsuranceClaimUpdate,
) -> dict:
    claim = get_latest_claim_for_patient_key(db, patient_key)
    update_claim(db, claim, payload)
    claim = get_claim_by_id(db, claim.id)
    return serialize_patient_bundle(db, claim)


def get_admission_insurance(db: Session, admission_id: int) -> dict:
    claim = (
        _claim_query(db)
        .filter(IpdInsuranceClaim.admission_id == admission_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Admission has no insurance profile")
    return serialize_claim(db, claim)


def update_admission_insurance(
    db: Session,
    admission_id: int,
    payload: IpdInsuranceClaimUpdate,
) -> dict:
    claim = (
        _claim_query(db)
        .filter(IpdInsuranceClaim.admission_id == admission_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Admission has no insurance profile")
    update_claim(db, claim, payload)
    claim = get_claim_by_id(db, claim.id)
    return serialize_claim(db, claim)


def add_payment(
    db: Session,
    claim: IpdInsuranceClaim,
    payload: IpdInsurancePaymentIn,
    *,
    kind: str,
) -> dict:
    entry = {
        "id": f"{kind}-{int(_now().timestamp() * 1000)}",
        "amount": float(payload.amount),
        "paid_at": payload.paid_at or _iso(_now()),
        "reference": payload.reference,
        "notes": payload.notes,
        "mode": payload.mode,
    }
    if kind == "insurance":
        payments = list(claim.insurance_payments or [])
        payments.append(entry)
        claim.insurance_payments = payments
    else:
        payments = list(claim.patient_payments or [])
        payments.append(entry)
        claim.patient_payments = payments
    claim.updated_at = _now()
    db.commit()
    db.refresh(claim)
    return serialize_claim(db, get_claim_by_id(db, claim.id))
