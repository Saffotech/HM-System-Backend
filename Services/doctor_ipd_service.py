from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.doctor_lab_test_order import LabTestOrder
from Models.doctor_prescriptions import Prescription
from Models.ipd import IpdAdmission, IpdDoctorVisit
from Models.patient import Patient
from Schemas.doctor_ipd_schema import DoctorIpdConsultationSaveRequest
from Schemas.doctor_lab_test_schema import LabTestCreate
from Services import doctor_helpers as h
from Services.doctor_lab_test_service import create_lab_test_service
from Services.doctor_prescription_service import (
    create_prescription_for_admission,
    serialize_prescription,
)


_STATUS_ALIASES = {
    "admit": "admitted",
    "admitted": "admitted",
    "discharge": "discharged",
    "discharged": "discharged",
    "cancelled": "cancelled",
}


def normalize_ipd_status(status: Optional[str]) -> Optional[str]:
    """Map UI aliases (admit/discharge) to DB status. None means no status filter."""
    if status is None:
        return "admitted"
    key = str(status).strip().lower()
    if not key or key == "admitted":
        return "admitted"
    if key == "all":
        return None
    mapped = _STATUS_ALIASES.get(key)
    if mapped is None:
        raise HTTPException(
            status_code=400,
            detail="status must be admitted, discharged, cancelled, or all",
        )
    return mapped


def list_doctor_ipd_admissions_service(
    db: Session,
    doctor_id: int,
    *,
    status: Optional[str] = "admitted",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    db_status = normalize_ipd_status(status)

    query = (
        db.query(IpdAdmission)
        .join(Patient, IpdAdmission.patient_id == Patient.id)
        .filter(
            IpdAdmission.doctor_id == doctor_id,
            Patient.is_active.is_(True),
        )
    )
    if db_status:
        query = query.filter(IpdAdmission.status == db_status)

    date_clause = h.admitted_between(from_date, to_date)
    if date_clause is not None:
        query = query.filter(date_clause)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.patient_uid.ilike(term),
                Patient.phone.ilike(term),
                IpdAdmission.admission_no.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(IpdAdmission.admitted_at.desc(), IpdAdmission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": h.admissions_to_dicts(db, rows, use_dashboard_status=False),
    }


def _build_ipd_visit_notes(*, symptoms: str, diagnosis: str, notes: str, follow_up) -> str:
    parts = []
    if symptoms:
        parts.append(f"Symptoms: {symptoms}")
    if diagnosis:
        parts.append(f"Diagnosis: {diagnosis}")
    if notes:
        parts.append(f"Notes: {notes}")
    if follow_up:
        parts.append(f"Follow-up: {follow_up.isoformat()}")
    return "\n".join(parts)


def _already_ordered_lab(detail: object) -> bool:
    return "already been ordered" in str(detail).lower()


def save_doctor_ipd_consultation_service(
    db: Session,
    admission_id: int,
    doctor_id: int,
    payload: DoctorIpdConsultationSaveRequest,
) -> dict:
    """Save IPD clinical notes, a visit, and optional real Rx + lab orders."""
    clinical = payload.clinical
    diagnosis = (clinical.diagnosis or "").strip()
    if not diagnosis:
        raise HTTPException(status_code=400, detail="Diagnosis is required")

    admission = (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.id == admission_id,
            IpdAdmission.doctor_id == doctor_id,
        )
        .with_for_update()
        .first()
    )
    if not admission:
        raise HTTPException(status_code=404, detail="IPD admission not found")
    if str(admission.status or "").strip().lower() != "admitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot save consultation for a closed admission",
        )

    symptoms = (clinical.symptoms or "").strip()
    notes = (clinical.notes or "").strip()
    follow_up = clinical.follow_up_date

    admission.diagnosis = diagnosis
    if notes:
        admission.notes = notes

    visit = IpdDoctorVisit(
        admission_id=admission.id,
        doctor_id=doctor_id,
        charge=0.0,
        notes=_build_ipd_visit_notes(
            symptoms=symptoms,
            diagnosis=diagnosis,
            notes=notes,
            follow_up=follow_up,
        )
        or None,
        recorded_by=doctor_id,
    )
    db.add(visit)

    prescription_out = None
    created_rx = None
    lab_outs = []
    created_lab_ids: list[int] = []
    seen_lab_names: set[str] = set()

    try:
        if payload.prescription is not None:
            rx_diagnosis = (payload.prescription.diagnosis or "").strip() or diagnosis
            if not rx_diagnosis:
                raise HTTPException(
                    status_code=400,
                    detail="prescription.diagnosis is required when saving a prescription",
                )
            if not payload.prescription.items:
                raise HTTPException(
                    status_code=400,
                    detail="prescription.items must not be empty",
                )
            created_rx = create_prescription_for_admission(
                db,
                admission,
                doctor_id=doctor_id,
                diagnosis=rx_diagnosis,
                items=payload.prescription.items,
                notes=payload.prescription.notes,
                commit=False,
            )
            prescription_out = serialize_prescription(created_rx).model_dump(mode="json")

        for lab in payload.lab_orders:
            test_name = (lab.test_name or "").strip()
            if not test_name and lab.lab_test_id is None:
                continue
            name_key = test_name.casefold()
            if name_key in seen_lab_names:
                continue
            seen_lab_names.add(name_key)
            lab_payload = LabTestCreate(
                admission_id=int(admission.id),
                test_name=test_name,
                lab_test_id=lab.lab_test_id,
                category=lab.category,
                department_id=lab.department_id,
                priority=lab.priority,
                clinical_notes=lab.clinical_notes,
            )
            try:
                lab_out = create_lab_test_service(
                    db,
                    lab_payload,
                    doctor_id,
                    commit=False,
                )
            except HTTPException as exc:
                if exc.status_code == 400 and _already_ordered_lab(exc.detail):
                    continue
                raise
            lab_outs.append(lab_out.model_dump(mode="json"))
            created_lab_ids.append(lab_out.id)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(admission)
    db.refresh(visit)

    if created_rx is not None:
        from Services.pharmacy_notification_helpers import (
            notify_pharmacists_prescription_created,
        )

        notified_rx = (
            db.query(Prescription)
            .options(joinedload(Prescription.items))
            .filter(Prescription.id == created_rx.id)
            .first()
        )
        if notified_rx is not None:
            notify_pharmacists_prescription_created(
                db, notified_rx, doctor_id=doctor_id
            )

    if created_lab_ids:
        from Services.lab_notification_helpers import notify_lab_techs_order_created

        for order in (
            db.query(LabTestOrder)
            .filter(LabTestOrder.id.in_(created_lab_ids))
            .all()
        ):
            notify_lab_techs_order_created(db, order, doctor_id=doctor_id)

    visited_at = visit.visited_at
    return {
        "success": True,
        "message": "IPD consultation saved",
        "admission": h.with_nurse_names(
            db,
            [h.admission_to_dict(db, admission, use_dashboard_status=False)],
        )[0],
        "visit": {
            "id": visit.id,
            "admission_id": visit.admission_id,
            "doctor_id": visit.doctor_id,
            "visited_at": visited_at.isoformat() if visited_at else None,
            "charge": float(visit.charge or 0),
            "notes": visit.notes,
        },
        "prescription": prescription_out,
        "lab_orders": lab_outs,
    }
