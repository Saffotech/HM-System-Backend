"""Resolve or create an appointment for nurse vitals/notes on bed patients."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.opd_billing import Appointment, AppointmentStatus, Bed
from Models.patient import Patient
from Models.role import Role
from Models.user import User
from Services import appointment_service as apt_svc


def _find_department_doctor_id(db: Session, department_id: int | None) -> int | None:
    """Pick an active doctor (optionally in the bed/department)."""
    doctor_role = db.query(Role).filter(Role.name == "doctor").first()
    q = db.query(User).filter(User.is_active.is_(True), User.deleted_at.is_(None))
    if doctor_role:
        q = q.filter(User.role_id == doctor_role.id)
    if department_id is not None:
        in_dept = q.filter(User.department_id == department_id).first()
        if in_dept:
            return in_dept.id
    any_doctor = q.first()
    return any_doctor.id if any_doctor else None


def resolve_appointment_for_nurse_care(
    db: Session,
    *,
    patient_id: int | None = None,
    appointment_id: int | None = None,
    created_by: int,
) -> Appointment:
    """
    Prefer explicit appointment_id.
    Else find latest non-cancelled appointment for patient.
    Else, if patient is on an occupied bed, create a nurse-care walk-in appointment.
    """
    if appointment_id is not None:
        apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not apt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if patient_id is not None and apt.patient_id != patient_id:
            raise HTTPException(
                status_code=400,
                detail="Appointment does not belong to this patient",
            )
        return apt

    if patient_id is None:
        raise HTTPException(
            status_code=400,
            detail="appointment_id or patient_id is required",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_active.is_(True))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.status != AppointmentStatus.cancelled,
        )
        .order_by(Appointment.scheduled_at.desc())
        .first()
    )
    if existing:
        return existing

    bed = (
        db.query(Bed)
        .filter(Bed.patient_id == patient_id, Bed.status == "occupied")
        .order_by(Bed.admitted_at.desc())
        .first()
    )
    if not bed:
        raise HTTPException(
            status_code=400,
            detail=(
                "patient_id only allowed for occupied-bed patients "
                "(or provide appointment_id for OPD)."
            ),
        )

    prior = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
        .first()
    )

    department_id = bed.department_id or (prior.department_id if prior else None)
    doctor_id = prior.doctor_id if prior else None
    if doctor_id is None:
        doctor_id = _find_department_doctor_id(db, department_id)

    if department_id is None:
        # Fall back to doctor's department
        if doctor_id:
            doctor = db.query(User).filter(User.id == doctor_id).first()
            department_id = doctor.department_id if doctor else None

    if not doctor_id or not department_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot link nurse care: bed patient has no doctor/department. "
                "Assign bed department or book an OPD appointment."
            ),
        )

    return apt_svc.create_walk_in_appointment(
        db,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        created_by=created_by,
        reason="Nurse care — bed patient",
    )


def patient_is_bed_assigned(db: Session, patient_id: int) -> bool:
    return (
        db.query(Bed)
        .filter(Bed.patient_id == patient_id, Bed.status == "occupied")
        .first()
        is not None
    )
