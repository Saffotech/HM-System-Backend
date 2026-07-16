"""Handover create/update/submit/take-over workflow."""
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

def create_handover_service(
    db: Session,
    handover_data: ShiftHandoverCreate,
    nurse_id: int
):

    if handover_data.department_id:

        department = (db.query(Department)
            .filter(Department.id ==handover_data.department_id)
            .first()
        )

        if not department:
            raise HTTPException(
                status_code=404,
                detail="Department not found"
            )

    handover_uid = (_generate_handover_uid(db))

    handover = ShiftHandover(

        handover_uid=handover_uid,
        outgoing_nurse_id=nurse_id,
        department_id=handover_data.department_id,
        ward_name=handover_data.ward_name,
        shift_date=handover_data.shift_date or _now().date(),
        shift_start=handover_data.shift_start,
        shift_end=handover_data.shift_end,
        general_notes=handover_data.general_notes,
        status=HandoverStatus.PENDING,
        created_by=nurse_id,
        updated_by=nurse_id
    )

    try:

        db.add(handover)
        db.commit()
        db.refresh(handover)


    except Exception as e:

        db.rollback()
        print("HANDOVER ERROR:", repr(e))
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    return handover

# ==========================================================
# BULK ADD HANDOVER PATIENTS
# ==========================================================

def update_handover_service(
    db: Session,
    handover_id: int,
    handover_data: ShiftHandoverUpdate,
    nurse_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (db.query(ShiftHandover)
        .filter(ShiftHandover.id == handover_id)
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own handover"
        )

    # ======================================================
    # SUBMITTED LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    # ======================================================
    # DEPARTMENT VALIDATION
    # ======================================================

    if handover_data.department_id:

        department = (
            db.query(Department)
            .filter(
                Department.id ==
                handover_data.department_id
            )
            .first()
        )

        if not department:
            raise HTTPException(
                status_code=404,
                detail="Department not found"
            )

    # ======================================================
    # UPDATE DATA
    # ======================================================

    update_data = (
        handover_data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in update_data.items():
        setattr(
            handover,
            field,
            value
        )

    handover.updated_by = nurse_id

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover)

        db.commit()

        db.refresh(handover)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update handover"
        )

    return handover

# ==========================================================
# UPDATE HANDOVER PATIENT
# ==========================================================

def submit_handover_service(
    db: Session,
    handover_id: int,
    nurse_id: int
):

    # ======================================================
    # HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
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

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only submit your own handover"
        )

    # ======================================================
    # ALREADY SUBMITTED
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Handover already submitted"
        )

    # ======================================================
    # PATIENT VALIDATION
    # ======================================================

    patient_count = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.handover_id
            == handover.id
        )
        .count()
    )

    if patient_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot submit handover "
                "without patient summaries"
            )
        )

    # Fill any blank care fields from live clinical data before locking
    patients = (
        db.query(ShiftHandoverPatient)
        .filter(ShiftHandoverPatient.handover_id == handover.id)
        .all()
    )
    for patient_row in patients:
        snapshot = _build_patient_care_snapshot(
            db,
            patient_row.patient_id,
            shift_date=handover.shift_date,
        )
        if not patient_row.patient_summary:
            patient_row.patient_summary = snapshot["patient_summary"]
        if not patient_row.pending_tasks:
            patient_row.pending_tasks = snapshot["pending_tasks"]
        if not patient_row.critical_alerts:
            patient_row.critical_alerts = snapshot["critical_alerts"]
        if not patient_row.medication_pending:
            patient_row.medication_pending = snapshot["medication_pending"]
        if not patient_row.doctor_instructions:
            patient_row.doctor_instructions = snapshot["doctor_instructions"]
        patient_row.updated_by = nurse_id

    # ======================================================
    # SUBMIT
    # ======================================================

    handover.status = (
        HandoverStatus.SUBMITTED
    )

    handover.submitted_at = (
        _now()
    )

    handover.updated_by = (
        nurse_id
    )

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover)

        db.commit()

        db.refresh(handover)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to submit handover"
        )

    return {
        "message":
            "Handover submitted successfully",

        "handover_id":
            handover.id,

        "handover_uid":
            handover.handover_uid,

        "status":
            handover.status
    }


# ==========================================================
# TAKE OVER HANDOVER (incoming nurse claims submitted form)
# ==========================================================

def take_over_handover_service(
    db: Session,
    handover_id: int,
    nurse_id: int,
    take_over_data: ShiftHandoverTakeOver | None = None,
):

    handover = (
        db.query(ShiftHandover)
        .filter(ShiftHandover.id == handover_id)
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Handover not found",
        )

    if handover.status != HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Only submitted handovers can be taken over",
        )

    if handover.outgoing_nurse_id == nurse_id:
        raise HTTPException(
            status_code=400,
            detail="Outgoing nurse cannot take over their own handover",
        )

    if handover.replacement_nurse_id is not None:
        current = (
            db.query(User)
            .filter(User.id == handover.replacement_nurse_id)
            .first()
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Handover already taken over by "
                f"{_user_display_name(current) or handover.replacement_nurse_id}"
            ),
        )

    nurse = (
        db.query(User)
        .options(joinedload(User.role_obj))
        .filter(User.id == nurse_id, User.is_active == True)
        .first()
    )

    if not _is_nurse_user(nurse):
        raise HTTPException(
            status_code=403,
            detail="Only a nurse can take over a handover",
        )

    notes = None
    if take_over_data:
        notes = take_over_data.take_over_notes

    handover.replacement_nurse_id = nurse_id
    handover.taken_over_at = _now()
    handover.take_over_notes = notes
    handover.updated_by = nurse_id

    try:
        db.add(handover)
        db.commit()
        db.refresh(handover)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to take over handover",
        )

    outgoing = (
        db.query(User)
        .filter(User.id == handover.outgoing_nurse_id)
        .first()
    )

    notify_nurse_handover_taken_over(
        db,
        outgoing_nurse_id=handover.outgoing_nurse_id,
        title="Handover taken over",
        message=(
            f"{_user_display_name(nurse) or 'A nurse'} took over your handover "
            f"{handover.handover_uid}."
            + (
                f"\nNotes: {notes}"
                if notes
                else ""
            )
        ),
        handover_id=handover.id,
        created_by=nurse_id,
        created_by_name=_user_display_name(nurse),
    )

    return {
        "message": "Handover taken over successfully",
        "handover_id": handover.id,
        "handover_uid": handover.handover_uid,
        "status": handover.status,
        "outgoing_nurse_id": handover.outgoing_nurse_id,
        "outgoing_nurse": _user_display_name(outgoing),
        "replacement_nurse_id": handover.replacement_nurse_id,
        "replacement_nurse": _user_display_name(nurse),
        "taken_over_at": handover.taken_over_at,
        "take_over_notes": handover.take_over_notes,
    }


# ==========================================================
# HANDOVER LIST
# ==========================================================

