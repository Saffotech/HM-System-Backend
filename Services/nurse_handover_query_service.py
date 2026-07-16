"""Handover list and detail queries."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload, aliased

from Models.department import Department
from Models.nurse_shift_handover import (
    ShiftHandover,
    ShiftHandoverPatient,
    HandoverStatus,
)
from Models.opd_billing import Bed
from Models.patient import Patient
from Models.user import User
from Schemas.nurse_shift_handover_schema import (
    ShiftHandoverCreate,
    ShiftHandoverUpdate,
    ShiftHandoverPatientUpdate,
    ShiftHandoverPatientsBulkCreate,
    ShiftHandoverTakeOver,
)
from Services.nurse_handover_helpers import (
    _now,
    _generate_handover_uid,
    _user_display_name,
    _is_nurse_user,
    _build_patient_care_snapshot,
)
from Services.notification_service import notify_nurse_handover_taken_over

def get_handover_list_service(
    db: Session,

    handover_uid: str | None = None,

    patient_id: int | None = None,
    patient_uid: str | None = None,

    patient_name: str | None = None,

    status: str | None = None,

    ward_name: str | None = None,

    shift_date: date | None = None,

    outgoing_nurse_id: int | None = None,
    outgoing_nurse_name: str | None = None,

    replacement_nurse_id: int | None = None,
    taken_over: bool | None = None,

    page: int = 1,
    page_size: int = 20
):

    # ======================================================
    # PAGINATION VALIDATION
    # ======================================================

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be greater than 0"
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Page size must be between 1 and 100"
        )

    OutgoingNurse = aliased(User)
    ReplacementNurse = aliased(User)

    # ======================================================
    # BASE QUERY
    # ======================================================

    query = (
        db.query(ShiftHandover)
        .outerjoin(
            ShiftHandoverPatient,
            ShiftHandoverPatient.handover_id
            == ShiftHandover.id
        )
        .outerjoin(
            Patient,
            Patient.id
            == ShiftHandoverPatient.patient_id
        )
        .outerjoin(
            OutgoingNurse,
            OutgoingNurse.id == ShiftHandover.outgoing_nurse_id,
        )
        .outerjoin(
            ReplacementNurse,
            ReplacementNurse.id == ShiftHandover.replacement_nurse_id,
        )
    )

    # ======================================================
    # FILTERS
    # ======================================================

    if handover_uid:
        query = query.filter(
            ShiftHandover.handover_uid.ilike(
                f"%{handover_uid}%"
            )
        )

    if patient_id:
        query = query.filter(
            ShiftHandoverPatient.patient_id
            == patient_id
        )

    if patient_uid:
        query = query.filter(
            Patient.patient_uid.ilike(
                f"%{patient_uid}%"
            )
        )

    if patient_name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(
                    f"%{patient_name}%"
                ),
                Patient.last_name.ilike(
                    f"%{patient_name}%"
                )
            )
        )

    if status:
        query = query.filter(
            ShiftHandover.status == status
        )

    if ward_name:
        query = query.filter(
            ShiftHandover.ward_name.ilike(
                f"%{ward_name}%"
            )
        )

    if shift_date:
        query = query.filter(
            ShiftHandover.shift_date
            == shift_date
        )

    if outgoing_nurse_id:
        query = query.filter(
            ShiftHandover.outgoing_nurse_id
            == outgoing_nurse_id
        )

    if outgoing_nurse_name:
        like = f"%{outgoing_nurse_name}%"
        query = query.filter(
            or_(
                OutgoingNurse.first_name.ilike(like),
                OutgoingNurse.last_name.ilike(like),
                func.concat(
                    OutgoingNurse.first_name,
                    " ",
                    func.coalesce(OutgoingNurse.last_name, ""),
                ).ilike(like),
            )
        )

    if replacement_nurse_id:
        query = query.filter(
            ShiftHandover.replacement_nurse_id
            == replacement_nurse_id
        )

    if taken_over is True:
        query = query.filter(
            ShiftHandover.replacement_nurse_id.isnot(None)
        )
    elif taken_over is False:
        query = query.filter(
            ShiftHandover.replacement_nurse_id.is_(None)
        )

    # ======================================================
    # TOTAL COUNT (distinct handovers)
    # ======================================================

    total_records = (
        query.with_entities(ShiftHandover.id)
        .distinct()
        .count()
    )

    # ======================================================
    # PAGINATION
    # ======================================================

    handover_ids = [
        row[0]
        for row in (
            query.with_entities(
                ShiftHandover.id,
                ShiftHandover.created_at,
            )
            .distinct()
            .order_by(ShiftHandover.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    ]

    if not handover_ids:
        return {
            "total_records": total_records,
            "page": page,
            "page_size": page_size,
            "data": [],
        }

    records = (
        db.query(ShiftHandover)
        .options(
            joinedload(ShiftHandover.outgoing_nurse),
            joinedload(ShiftHandover.replacement_nurse),
        )
        .filter(ShiftHandover.id.in_(handover_ids))
        .all()
    )

    record_map = {h.id: h for h in records}
    ordered = [record_map[hid] for hid in handover_ids if hid in record_map]

    # ======================================================
    # RESPONSE
    # ======================================================

    data = []

    for handover in ordered:

        patient_count = (
            db.query(
                ShiftHandoverPatient
            )
            .filter(
                ShiftHandoverPatient.handover_id
                == handover.id
            )
            .count()
        )

        data.append({

            "handover_id":
                handover.id,

            "handover_uid":
                handover.handover_uid,

            "outgoing_nurse_id":
                handover.outgoing_nurse_id,

            "outgoing_nurse":
                _user_display_name(handover.outgoing_nurse),

            "replacement_nurse_id":
                handover.replacement_nurse_id,

            "replacement_nurse":
                _user_display_name(handover.replacement_nurse),

            "ward_name":
                handover.ward_name,

            "shift_date":
                handover.shift_date,

            "status":
                handover.status,

            "patient_count":
                patient_count,

            "submitted_at":
                handover.submitted_at,

            "taken_over_at":
                handover.taken_over_at,

            "created_at":
                handover.created_at
        })

    return {

        "total_records":
            total_records,

        "page":
            page,

        "page_size":
            page_size,

        "data":
            data
    }


# ==========================================================
# HANDOVER DETAIL
# ==========================================================

def get_handover_detail_service(
    db: Session,
    handover_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .options(
            joinedload(ShiftHandover.outgoing_nurse),
            joinedload(ShiftHandover.replacement_nurse),
        )
        .filter(
            ShiftHandover.id == handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    patients = (
        db.query(
            ShiftHandoverPatient
        )
        .options(
            joinedload(ShiftHandoverPatient.patient)
        )
        .filter(
            ShiftHandoverPatient.handover_id
            == handover.id
        )
        .order_by(
            ShiftHandoverPatient.created_at.asc()
        )
        .all()
    )

    patient_data = []

    for patient in patients:

        patient_data.append({

            "id":
                patient.id,

            "patient_id":
                patient.patient_id,

            "patient_uid":
                patient.patient.patient_uid
                if patient.patient else None,

            "patient_name":
                patient.patient_name,

            "bed_number":
                patient.bed_number,

            "patient_summary":
                patient.patient_summary,

            "pending_tasks":
                patient.pending_tasks,

            "critical_alerts":
                patient.critical_alerts,

            "medication_pending":
                patient.medication_pending,

            "doctor_instructions":
                patient.doctor_instructions,

            "created_at":
                patient.created_at
        })

    return {

        "handover_id":
            handover.id,

        "handover_uid":
            handover.handover_uid,

        "outgoing_nurse_id":
            handover.outgoing_nurse_id,

        "outgoing_nurse":
            _user_display_name(handover.outgoing_nurse),

        "replacement_nurse_id":
            handover.replacement_nurse_id,

        "replacement_nurse":
            _user_display_name(handover.replacement_nurse),

        "department_id":
            handover.department_id,

        "ward_name":
            handover.ward_name,

        "shift_date":
            handover.shift_date,

        "shift_start":
            handover.shift_start,

        "shift_end":
            handover.shift_end,

        "general_notes":
            handover.general_notes,

        "status":
            handover.status,

        "submitted_at":
            handover.submitted_at,

        "taken_over_at":
            handover.taken_over_at,

        "take_over_notes":
            handover.take_over_notes,

        "created_at":
            handover.created_at,

        "updated_at":
            handover.updated_at,

        "patients":
            patient_data
    }