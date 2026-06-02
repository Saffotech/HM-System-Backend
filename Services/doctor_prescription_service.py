from fastapi import HTTPException
from sqlalchemy.orm import Session
from Models.doctor_appointments import Appointment
from Models.doctor_prescriptions import Prescription,PrescriptionItem
from Schemas.doctor_prescription_schema import PrescriptionCreate

# ==========================================================
# Create Prescription Service
# ==========================================================

def create_prescription_service(

    db: Session,
    prescription_data: PrescriptionCreate,
    doctor_id: int
):

    # ======================================================
    # Check Appointment Exists
    # ======================================================

    appointment = (db.query(Appointment)
        .filter(Appointment.id == (
                prescription_data.appointment_id
            )
        ).first()
    )

    if not appointment:

        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    # ======================================================
    # Check Doctor Ownership
    # ======================================================

    if appointment.doctor_id != doctor_id:

        raise HTTPException(
            status_code=403,
            detail=(
                "You can only create "
                "prescriptions for your "
                "own appointments"
            )
        )

    # ======================================================
    # Check Consultation Completed
    # ======================================================

    if appointment.status != "completed":

        raise HTTPException(
            status_code=400,
            detail=(
                "Prescription can only "
                "be created after "
                "consultation completion"
            )
        )

    # ======================================================
    # Prevent Duplicate Prescription
    # ======================================================

    existing_prescription = (db.query(Prescription)
        .filter(Prescription.appointment_id == (
                appointment.id
            )
        ).first()
    )

    if existing_prescription:

        raise HTTPException(
            status_code=400,
            detail=(
                "Prescription already "
                "exists for this "
                "appointment"
            )
        )

    # ======================================================
    # Create Prescription
    # ======================================================

    new_prescription = Prescription(

        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=doctor_id,
        diagnosis=(prescription_data.diagnosis),
        notes=prescription_data.notes
    )

    db.add(new_prescription)

    db.flush()

    # ======================================================
    # Create Prescription Items
    # ======================================================

    for item in prescription_data.items:

        prescription_item = PrescriptionItem(

            prescription_id=(
                new_prescription.id
            ),

            medicine_name=item.medicine_name,

            dosage=item.dosage,

            frequency=item.frequency,

            duration=item.duration,

            instructions=item.instructions
        )

        db.add(prescription_item)

    db.commit()

    db.refresh(new_prescription)

    return new_prescription


# ==========================================================
# Get Prescription By ID
# ==========================================================

def get_prescription_by_id_service(

    db: Session,
    prescription_id: int,
    doctor_id: int
):

    prescription = (
        db.query(Prescription)
        .filter(
            Prescription.id == prescription_id,
            Prescription.doctor_id == doctor_id
        )
        .first()
    )

    if not prescription:

        raise HTTPException(
            status_code=404,
            detail="Prescription not found"
        )

    return prescription


# ==========================================================
# Get Patient Prescription History
# ==========================================================

def get_patient_prescriptions_service(

    db: Session,
    patient_id: int,
    doctor_id: int
):

    prescriptions = (
        db.query(Prescription)
        .filter(
            Prescription.patient_id == patient_id,
            Prescription.doctor_id == doctor_id
        )
        .order_by(
            Prescription.created_at.desc()
        )
        .all()
    )

    return prescriptions


# ==========================================================
# Update Prescription Service
# ==========================================================

def update_prescription_service(

    db: Session,
    prescription_id: int,
    prescription_data: PrescriptionCreate,
    doctor_id: int
):

    # ======================================================
    # Find Prescription
    # ======================================================

    prescription = (
        db.query(Prescription)
        .filter(
            Prescription.id == prescription_id,
            Prescription.doctor_id == doctor_id
        )
        .first()
    )

    if not prescription:

        raise HTTPException(
            status_code=404,
            detail="Prescription not found"
        )

    # ======================================================
    # Update Main Prescription
    # ======================================================

    prescription.diagnosis = (
        prescription_data.diagnosis
    )

    prescription.notes = (
        prescription_data.notes
    )

    # ======================================================
    # Delete Old Prescription Items
    # ======================================================

    (
        db.query(PrescriptionItem)
        .filter(
            PrescriptionItem.prescription_id == (
                prescription.id
            )
        )
        .delete()
    )

    # ======================================================
    # Add Updated Prescription Items
    # ======================================================

    for item in prescription_data.items:

        updated_item = PrescriptionItem(

            prescription_id=prescription.id,

            medicine_name=item.medicine_name,

            dosage=item.dosage,

            frequency=item.frequency,

            duration=item.duration,

            instructions=item.instructions
        )

        db.add(updated_item)

    db.commit()

    db.refresh(prescription)

    return prescription


# ==========================================================
# Delete Prescription Service
# ==========================================================

def delete_prescription_service(

    db: Session,
    prescription_id: int,
    doctor_id: int
):

    prescription = (
        db.query(Prescription)
        .filter(
            Prescription.id == prescription_id,
            Prescription.doctor_id == doctor_id
        )
        .first()
    )

    if not prescription:

        raise HTTPException(
            status_code=404,
            detail="Prescription not found"
        )

    db.delete(prescription)

    db.commit()

    return {
        "message": (
            "Prescription deleted "
            "successfully"
        )
    }