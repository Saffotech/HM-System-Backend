"""OPD appointment booking."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.department import Department
from Models.opd_billing import Appointment
from Models.patient import Patient
from Models.user import User
from Schemas.opd_schema import AppointmentCreate, AppointmentOut, AppointmentUpdate
from Services import opd_helpers as h


def _appointment_out(db: Session, apt: Appointment) -> AppointmentOut:
    patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
    doctor = db.query(User).filter(User.id == apt.doctor_id).first()
    dept = db.query(Department).filter(Department.id == apt.department_id).first()
    return AppointmentOut(
        id=apt.id,
        appointment_uid=apt.appointment_uid,
        patient_id=apt.patient_id,
        patient_name=h.display_name(patient.first_name, patient.last_name) if patient else "",
        patient_uid=patient.patient_uid if patient else "",
        doctor_id=apt.doctor_id,
        doctor_name=h.display_name(doctor.first_name, doctor.last_name, prefix="Dr. ") if doctor else "",
        department_id=apt.department_id,
        department_name=dept.name if dept else "",
        scheduled_at=apt.scheduled_at.isoformat() if apt.scheduled_at else "",
        reason=apt.reason,
        notes=apt.notes,
        appointment_type=apt.appointment_type,
        status=apt.status,
    )


def create_appointment(db: Session, data: AppointmentCreate, created_by: int) -> AppointmentOut:
    patient = h.get_patient(db, data.patient_id)
    h.get_department(db, data.department_id)
    h.get_doctor_in_department(db, data.doctor_id, data.department_id)

    apt = Appointment(
        appointment_uid=h.next_appointment_uid(db),
        patient_id=patient.id,
        doctor_id=data.doctor_id,
        department_id=data.department_id,
        scheduled_at=data.scheduled_at,
        reason=data.reason,
        notes=data.notes,
        appointment_type=data.appointment_type,
        status="scheduled",
        created_by=created_by,
    )
    db.add(apt)
    db.commit()
    db.refresh(apt)
    return _appointment_out(db, apt)


def list_appointments(
    db: Session,
    status: Optional[str] = None,
    date_from=None,
    date_to=None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q = db.query(Appointment).order_by(Appointment.scheduled_at.asc())
    if status:
        q = q.filter(Appointment.status == status)
    if date_from:
        q = q.filter(Appointment.scheduled_at >= date_from)
    if date_to:
        q = q.filter(Appointment.scheduled_at <= date_to)

    total = q.count()
    rows = q.offset((page - 1) * limit).limit(limit).all()

    counts = {"scheduled": 0, "completed": 0, "cancelled": 0}
    for s in counts:
        counts[s] = db.query(Appointment).filter(Appointment.status == s).count()

    return {
        "counts": counts,
        "total": total,
        "page": page,
        "limit": limit,
        "appointments": [_appointment_out(db, a) for a in rows],
    }


def update_appointment(db: Session, appointment_id: int, data: AppointmentUpdate) -> AppointmentOut:
    apt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(apt, key, value)

    db.commit()
    db.refresh(apt)
    return _appointment_out(db, apt)


def cancel_appointment(db: Session, appointment_id: int) -> AppointmentOut:
    return update_appointment(
        db, appointment_id, AppointmentUpdate(status="cancelled")
    )


def doctor_availability(db: Session, doctor_id: int, department_id: int, date_str: str) -> dict:
    h.get_doctor_in_department(db, doctor_id, department_id)
    from datetime import datetime

    day = datetime.fromisoformat(date_str).replace(tzinfo=h.IST)
    day_end = day.replace(hour=23, minute=59, second=59)

    booked = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at >= day,
            Appointment.scheduled_at <= day_end,
            Appointment.status == "scheduled",
        )
        .all()
    )
    slots = []
    for hour in range(9, 17):
        for minute in (0, 30):
            slot_time = day.replace(hour=hour, minute=minute)
            taken = any(a.scheduled_at == slot_time for a in booked)
            slots.append({
                "time": slot_time.strftime("%H:%M"),
                "status": "booked" if taken else "available",
            })

    return {"doctor_id": doctor_id, "date": date_str, "slots": slots}
