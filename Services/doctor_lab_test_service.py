from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from Models.doctor_appointments import Appointment
from Models.doctor_lab_test_order import (
    LabTestOrder,
    LabTestStatus
)

from Schemas.doctor_lab_test_schema import (
    LabTestCreate,
    LabTestUpdate
)


# ==========================================================
# Create Lab Test
# ==========================================================

def create_lab_test_service(
    db: Session,
    payload: LabTestCreate,
    doctor_id: int
):

    appointment = db.query(Appointment).filter(
        Appointment.id == payload.appointment_id,
        Appointment.doctor_id == doctor_id
    ).first()

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found or does not belong to this doctor"
        )

    # Prevent duplicate active test orders
    existing_test = db.query(LabTestOrder).filter(
        LabTestOrder.appointment_id == payload.appointment_id,
        LabTestOrder.test_name == payload.test_name,
        LabTestOrder.status != LabTestStatus.CANCELLED
    ).first()

    if existing_test:
        raise HTTPException(
            status_code=400,
            detail="This test has already been ordered for this appointment"
        )

    lab_test = LabTestOrder(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        patient_name=appointment.patient_name,
        patient_uhid=appointment.patient_uhid,
        doctor_id=doctor_id,
        test_name=payload.test_name,
        category=payload.category,
        priority=payload.priority,
        clinical_notes=payload.clinical_notes,
        status=LabTestStatus.ORDERED
    )

    db.add(lab_test)
    db.commit()
    db.refresh(lab_test)

    return lab_test


# ==========================================================
# View All / Search Lab Tests
# ==========================================================

def get_lab_tests_service(
    db: Session,
    doctor_id: int,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20
):

    query = db.query(LabTestOrder).filter(
        LabTestOrder.doctor_id == doctor_id
    )

    if search:

        search = search.strip()

        filters = [
            LabTestOrder.patient_name.ilike(f"%{search}%"),
            LabTestOrder.patient_uhid.ilike(f"%{search}%"),
            LabTestOrder.test_name.ilike(f"%{search}%")
        ]

        if search.isdigit():
            filters.extend([
                LabTestOrder.id == int(search),
                LabTestOrder.patient_id == int(search)
            ])

        query = query.filter(
            or_(*filters)
        )

    return (
        query.order_by(
            LabTestOrder.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


# ==========================================================
# Update Lab Test
# ==========================================================

def update_lab_test_service(
    db: Session,
    test_id: int,
    payload: LabTestUpdate,
    doctor_id: int
):

    test = db.query(LabTestOrder).filter(
        LabTestOrder.id == test_id,
        LabTestOrder.doctor_id == doctor_id
    ).first()

    if test is None:
        raise HTTPException(
            status_code=404,
            detail="Lab test not found"
        )

    if test.status != LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Only ordered tests can be updated"
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )

    for field, value in update_data.items():
        setattr(test, field, value)

    db.commit()
    db.refresh(test)

    return test


# ==========================================================
# Cancel Lab Test
# ==========================================================

def cancel_lab_test_service(
    db: Session,
    test_id: int,
    doctor_id: int
):

    test = db.query(LabTestOrder).filter(
        LabTestOrder.id == test_id,
        LabTestOrder.doctor_id == doctor_id
    ).first()

    if test is None:
        raise HTTPException(
            status_code=404,
            detail="Lab test not found"
        )

    if test.status != LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Only ordered tests can be cancelled"
        )

    test.status = LabTestStatus.CANCELLED

    db.commit()
    db.refresh(test)

    return {
        "message": "Lab test cancelled successfully"
    }