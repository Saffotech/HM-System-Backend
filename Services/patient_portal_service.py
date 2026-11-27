"""OPD booking for a patient who signed in themselves.

The desk books with POST /opd/appointments and then creates a bill.
This service does those two steps for the logged-in patient only:

1. Book — department, doctor, time, reason. No token yet.
2. Bill — registration fee, consultation fee, and GST from hospital pricing.
3. Pay — same payment recorder the desk uses. The token is on the bill.

A patient cannot pass another person's id. Every query starts from
patients.user_id of the current login.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.department import Department
from Models.opd_billing import Appointment
from Models.patient import OpdVisit, Patient
from Models.user import User
from Schemas.opd_schema import AppointmentCreate, CollectPayment, VisitBillingFields
from Schemas.patient_portal_schema import PatientBookAppointment, PatientPayAppointment
from Services import appointment_service, opd_service, opd_settings_service


def require_patient_user(user: User) -> None:
    role_name = user.role_obj.name if user.role_obj else ""
    if role_name != "patient":
        raise HTTPException(status_code=403, detail="Only a patient can use this")


def patient_for_user(db: Session, user: User) -> Patient:
    """The hospital patient row created at self-register, or linked by the desk."""
    require_patient_user(user)
    patient = (
        db.query(Patient)
        .filter(Patient.user_id == user.id, Patient.is_active.is_(True))
        .first()
    )
    if patient is None:
        raise HTTPException(
            status_code=404,
            detail="No hospital patient record is linked to this login",
        )
    return patient


def list_departments(db: Session, user: User) -> dict:
    patient_for_user(db, user)
    rows = (
        db.query(Department)
        .filter(Department.is_active.is_(True), Department.kind == "doctor")
        .order_by(Department.name)
        .all()
    )
    return {
        "departments": [
            {"id": row.id, "name": row.name, "code": row.code}
            for row in rows
        ]
    }


def list_doctors(db: Session, user: User, department_id: int) -> dict:
    patient_for_user(db, user)
    return opd_service.list_department_doctors_with_fees(db, department_id)


def list_slots(db: Session, user: User, doctor_id: int, department_id: int, day: str) -> dict:
    patient_for_user(db, user)
    return appointment_service.doctor_availability(db, doctor_id, department_id, day)


def book(db: Session, user: User, data: PatientBookAppointment) -> dict:
    """Create the appointment. Payment is a later call."""
    patient = patient_for_user(db, user)
    created = appointment_service.create_appointment(
        db,
        AppointmentCreate(
            patient_id=patient.id,
            doctor_id=data.doctor_id,
            department_id=data.department_id,
            scheduled_at=data.scheduled_at,
            reason=data.reason,
            appointment_type="opd",
        ),
        user.id,
    )
    return created.model_dump()


def my_appointments(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    return appointment_service.list_appointments(db, patient_id=patient.id, limit=50)


def _own_appointment(db: Session, patient: Patient, appointment_id: int) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient.id,
        )
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


def _registration_fee_for(db: Session, patient: Patient, pricing) -> float:
    """First OPD visit pays registration. A later visit does not."""
    already_visited = (
        db.query(OpdVisit.id)
        .filter(OpdVisit.patient_id == patient.id, OpdVisit.status != "cancelled")
        .first()
    )
    if already_visited is not None:
        return 0.0
    return float(pricing.registration_fee)


def bill_preview(db: Session, user: User, appointment_id: int) -> dict:
    """Show the amount before creating the bill. Nothing is saved."""
    patient = patient_for_user(db, user)
    appointment = _own_appointment(db, patient, appointment_id)
    pricing = opd_settings_service.get_pricing(db)
    registration_fee, consultation_fee, gst_percent = opd_settings_service.resolve_visit_fees(
        pricing,
        doctor_id=appointment.doctor_id,
        department_id=appointment.department_id,
        registration_fee=_registration_fee_for(db, patient, pricing),
    )
    subtotal = registration_fee + consultation_fee
    gst_amount = round(subtotal * gst_percent / 100, 2)
    return {
        "appointment_id": appointment.id,
        "registration_fee": registration_fee,
        "consultation_fee": consultation_fee,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "grand_total": round(subtotal + gst_amount, 2),
    }


def create_bill(db: Session, user: User, appointment_id: int):
    """Create the unpaid visit and token. The patient pays on the next call."""
    patient = patient_for_user(db, user)
    appointment = _own_appointment(db, patient, appointment_id)
    existing = appointment_service._visit_for_appointment(db, appointment)
    if existing is not None:
        return opd_service.ensure_bill_for_appointment(db, appointment.id, user.id)

    pricing = opd_settings_service.get_pricing(db)
    registration_fee = _registration_fee_for(db, patient, pricing)
    billing = VisitBillingFields(
        department_id=appointment.department_id,
        doctor_id=appointment.doctor_id,
        registration_fee=registration_fee,
        consultation_fee=0.0,
        gst_percent=float(pricing.gst_percent),
    )
    visit = opd_service.create_visit(
        db,
        patient,
        billing,
        user.id,
        pay_later=True,
    )
    visit.appointment_id = appointment.id
    if appointment.scheduled_at is not None:
        visit.visit_date = appointment.scheduled_at
    db.commit()
    db.refresh(visit)
    return {
        "message": "Bill created. Pay to confirm the visit.",
        "patient_id": patient.id,
        "patient_uid": patient.patient_uid,
        "bill_number": visit.bill_number,
        "token_number": visit.token_number,
        "visit_id": visit.id,
        "grand_total": visit.grand_total,
        "payment_status": visit.payment_status,
        "appointment_id": appointment.id,
        "appointment_uid": appointment.appointment_uid,
    }


def pay(db: Session, user: User, appointment_id: int, data: PatientPayAppointment) -> dict:
    patient = patient_for_user(db, user)
    appointment = _own_appointment(db, patient, appointment_id)
    visit = appointment_service._visit_for_appointment(db, appointment)
    if visit is None or visit.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Create the bill before paying")
    opd_settings_service.validate_payment_mode(db, payment_mode=data.payment_mode)
    return opd_service.collect_payment(
        db,
        visit.id,
        CollectPayment(
            payment_mode=data.payment_mode,
            paid_amount=data.paid_amount,
            transaction_reference=data.transaction_reference,
        ),
        user.id,
    )
