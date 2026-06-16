from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.doctor_prescriptions import Prescription, PrescriptionItem
from Models.opd_billing import Appointment
from Schemas.doctor_prescription_schema import PrescriptionCreate, PrescriptionItemCreate
from Services import doctor_helpers as h

def _pk(value: object) -> int:
    return int(value)


def _item(rx_id: int, item: PrescriptionItemCreate) -> PrescriptionItem:
    return PrescriptionItem(
        prescription_id=rx_id,
        medicine_name=item.medicine_name,
        dosage=item.dosage,
        frequency=item.frequency,
        duration=item.duration,
        instructions=item.instructions or "",
    )


def _add_items(db: Session, rx_id: int, items: list[PrescriptionItemCreate]) -> None:
    for item in items:
        db.add(_item(rx_id, item))


def _get_prescription(db: Session, prescription_id: int, doctor_id: int) -> Prescription:
    rx = (
        db.query(Prescription)
        .filter(Prescription.id == prescription_id, Prescription.doctor_id == doctor_id)
        .first()
    )
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return rx


def create_prescription_service(db: Session, prescription_data: PrescriptionCreate, doctor_id: int):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == prescription_data.appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.doctor_id != doctor_id:
        raise HTTPException(status_code=403, detail="You can only create prescriptions for your own appointments")
    if appointment.status != "completed":
        raise HTTPException(status_code=400, detail="Prescription can only be created after consultation completion")

    appt_id = _pk(appointment.id)
    if db.query(Prescription).filter(Prescription.appointment_id == appt_id).first():
        raise HTTPException(status_code=400, detail="Prescription already exists for this appointment")

    patient = h.get_patient(db, _pk(appointment.patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    rx = Prescription(
        appointment_id=appt_id,
        patient_id=_pk(appointment.patient_id),
        patient_name=h.display_name(patient.first_name, patient.last_name),
        doctor_id=doctor_id,
        diagnosis=prescription_data.diagnosis,
        status="pending",
        created_by=doctor_id,
    )
    rx.notes = prescription_data.notes
    db.add(rx)
    db.flush()
    _add_items(db, _pk(rx.id), prescription_data.items)
    db.commit()
    db.refresh(rx)
    return rx


def get_prescription_by_id_service(db: Session, prescription_id: int, doctor_id: int):
    return _get_prescription(db, prescription_id, doctor_id)


def get_patient_prescriptions_service(db: Session, patient_id: int, doctor_id: int):
    return (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id, Prescription.doctor_id == doctor_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )


def update_prescription_service(
    db: Session, prescription_id: int, prescription_data: PrescriptionCreate, doctor_id: int
):
    rx = _get_prescription(db, prescription_id, doctor_id)
    rx.diagnosis = prescription_data.diagnosis
    rx.notes = prescription_data.notes

    rx_id = _pk(rx.id)
    db.query(PrescriptionItem).filter(PrescriptionItem.prescription_id == rx_id).delete()
    _add_items(db, rx_id, prescription_data.items)
    db.commit()
    db.refresh(rx)
    return rx


def delete_prescription_service(db: Session, prescription_id: int, doctor_id: int):
    rx = _get_prescription(db, prescription_id, doctor_id)
    db.delete(rx)
    db.commit()
    return {"message": "Prescription deleted successfully"}
