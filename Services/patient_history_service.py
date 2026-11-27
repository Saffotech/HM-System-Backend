"""Hospital Records on the patient Profile tab.

OPD history = this patient's completed appointments.
IPD history = this patient's discharged admissions, plus the current one.

Clinical text (diagnosis, notes) is left out on purpose. The patient sees
who, where, and when. Reports and discharge documents are separate features.
"""

from sqlalchemy.orm import Session

from Models.department import Department
from Models.ipd import IpdAdmission
from Models.opd_billing import Appointment, AppointmentStatus
from Models.user import User
from Services import appointment_service
from Services import ipd_helpers as ipd_h
from Services.patient_portal_service import patient_for_user


def opd_history(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    rows = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.status == AppointmentStatus.completed,
        )
        .order_by(Appointment.scheduled_at.desc(), Appointment.id.desc())
        .all()
    )
    visit_map = appointment_service._load_visits_for_appointments(db, rows)
    outs = appointment_service._appointments_out_list(db, rows, visit_map)

    visits = []
    for out in outs:
        visit = visit_map.get(out.id)
        visits.append(
            {
                "appointment_id": out.id,
                "appointment_uid": out.appointment_uid,
                "scheduled_at": out.scheduled_at,
                "doctor_name": out.doctor_name,
                "department_name": out.department_name,
                "reason": out.reason,
                "token_number": visit.token_number if visit else None,
                "bill_number": out.bill_number,
                "payment_status": out.payment_status,
                "total_amount": out.total_amount,
            }
        )
    return {"total": len(visits), "visits": visits}


def _admission_item(
    db: Session,
    admission: IpdAdmission,
    departments: dict[int, Department],
) -> dict:
    department = departments.get(admission.department_id) if admission.department_id else None
    return {
        "admission_id": admission.id,
        "admission_no": admission.admission_no,
        "status": admission.status,
        "admitted_at": admission.admitted_at,
        "discharged_at": admission.discharged_at,
        "ward_name": admission.ward_name,
        "bed_number": admission.bed_number,
        "doctor_name": ipd_h.doctor_display(db, admission.doctor_id),
        "department_name": department.name if department else None,
        "payment_type": admission.payment_type,
    }


def ipd_history(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    rows = (
        db.query(IpdAdmission)
        .filter(
            IpdAdmission.patient_id == patient.id,
            IpdAdmission.status.in_(("admitted", "discharged")),
        )
        .order_by(IpdAdmission.admitted_at.desc(), IpdAdmission.id.desc())
        .all()
    )
    department_ids = {row.department_id for row in rows if row.department_id}
    departments = (
        {d.id: d for d in db.query(Department).filter(Department.id.in_(department_ids)).all()}
        if department_ids
        else {}
    )
    items = [_admission_item(db, row, departments) for row in rows]
    current = next((item for item in items if item["status"] == "admitted"), None)
    past = [item for item in items if item["status"] == "discharged"]
    return {
        "total": len(past),
        "current_admission": current,
        "admissions": past,
    }
