"""Handover patient row create/update/delete."""
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

def bulk_add_handover_patients_service(
    db: Session,
    handover_id: int,
    patient_data: ShiftHandoverPatientsBulkCreate,
    nurse_id: int
):

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
    # ONLY CREATOR CAN MODIFY
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own handover"
        )

    # ======================================================
    # SUBMITTED HANDOVER LOCK
    # ======================================================

    if handover.status == HandoverStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail="Submitted handover cannot be modified"
        )

    records_to_insert = []

    # ======================================================
    # PROCESS PATIENTS
    # ======================================================

    for item in patient_data.patients:

        patient = (db.query(Patient)
            .filter(Patient.id == item.patient_id,
                Patient.is_active == True
            ).first()
        )

        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient {item.patient_id} not found"
            )

        # ==================================================
        # DUPLICATE CHECK
        # ==================================================

        existing = (db.query(ShiftHandoverPatient)
            .filter(ShiftHandoverPatient.handover_id== handover_id,
                        ShiftHandoverPatient.patient_id== item.patient_id
            ).first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Patient "
                    f"{item.patient_id} "
                    f"already exists "
                    f"in handover"
                )
            )

        # ==================================================
        # BED SNAPSHOT
        # ==================================================

        bed = (db.query(Bed)
            .filter(Bed.patient_id == patient.id,
                Bed.status == "occupied"
            ).order_by(Bed.admitted_at.desc())
            .first()
        )

        patient_name = (
            f"{patient.first_name} "
            f"{patient.last_name or ''}"
        ).strip()

        snapshot = _build_patient_care_snapshot(
            db,
            patient.id,
            shift_date=handover.shift_date,
        )

        handover_patient = (
            ShiftHandoverPatient(

                handover_id=handover.id,
                patient_id=patient.id,
                patient_name=patient_name,
                bed_number=bed.bed_number

                if bed else None,

                patient_summary=(
                    item.patient_summary
                    if item.patient_summary is not None
                    else snapshot["patient_summary"]
                ),
                pending_tasks=(
                    item.pending_tasks
                    if item.pending_tasks is not None
                    else snapshot["pending_tasks"]
                ),
                critical_alerts=(
                    item.critical_alerts
                    if item.critical_alerts is not None
                    else snapshot["critical_alerts"]
                ),
                medication_pending=(
                    item.medication_pending
                    if item.medication_pending is not None
                    else snapshot["medication_pending"]
                ),
                doctor_instructions=(
                    item.doctor_instructions
                    if item.doctor_instructions is not None
                    else snapshot["doctor_instructions"]
                ),

                created_by=nurse_id,
                updated_by=nurse_id
            )
        )

        records_to_insert.append(
            handover_patient
        )
    try:
        db.add_all(records_to_insert)
        db.commit()

    except Exception:

        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=
            "Failed to add patients to handover"
        )

    return {
        "message":"Patients added successfully",
        "count":len(records_to_insert)
    }

# ==========================================================
# UPDATE HANDOVER
# ==========================================================

def update_handover_patient_service(
    db: Session,
    patient_summary_id: int,
    patient_data: ShiftHandoverPatientUpdate,
    nurse_id: int
):

    # ======================================================
    # PATIENT HANDOVER EXISTS
    # ======================================================

    handover_patient = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.id
            == patient_summary_id
        )
        .first()
    )

    if not handover_patient:
        raise HTTPException(
            status_code=404,
            detail="Patient handover record not found"
        )

    # ======================================================
    # PARENT HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .filter(
            ShiftHandover.id
            == handover_patient.handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Parent handover not found"
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
    # UPDATE DATA
    # ======================================================

    update_data = (
        patient_data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in update_data.items():
        setattr(
            handover_patient,
            field,
            value
        )

    handover_patient.updated_by = nurse_id

    # ======================================================
    # SAVE
    # ======================================================

    try:

        db.add(handover_patient)

        db.commit()

        db.refresh(handover_patient)

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to update patient handover"
        )

    return handover_patient

# ==========================================================
# DELETE HANDOVER PATIENT
# ==========================================================

def delete_handover_patient_service(
    db: Session,
    patient_summary_id: int,
    nurse_id: int
):

    # ======================================================
    # PATIENT HANDOVER EXISTS
    # ======================================================

    handover_patient = (
        db.query(ShiftHandoverPatient)
        .filter(
            ShiftHandoverPatient.id
            == patient_summary_id
        )
        .first()
    )

    if not handover_patient:
        raise HTTPException(
            status_code=404,
            detail="Patient handover record not found"
        )

    # ======================================================
    # PARENT HANDOVER EXISTS
    # ======================================================

    handover = (
        db.query(ShiftHandover)
        .filter(
            ShiftHandover.id
            == handover_patient.handover_id
        )
        .first()
    )

    if not handover:
        raise HTTPException(
            status_code=404,
            detail="Parent handover not found"
        )

    # ======================================================
    # OWNER VALIDATION
    # ======================================================

    if handover.outgoing_nurse_id != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own handover"
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
    # DELETE
    # ======================================================

    try:

        db.delete(handover_patient)

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to delete patient handover"
        )

    return {
        "message":
            "Patient removed from handover successfully"
    }


# ==========================================================
# SUBMIT HANDOVER
# ==========================================================

