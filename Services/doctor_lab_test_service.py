from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.doctor_lab_test_order import LabTestOrder, LabTestStatus
from Models.ipd import IpdAdmission
from Models.lab_result import LabResult
from Models.opd_billing import Appointment
from Models.patient import Patient, registration_source_value
from Schemas.doctor_lab_test_schema import (
    LabTestCreate,
    LabTestUpdate,
    LabTestListResponse,
    LabTestResponse,
)
from Services import doctor_helpers as h
from Services.lab_test_catalog_service import resolve_catalog_test
from Services.lab_department_helpers import resolve_lab_department_id
from Services.lab_notification_helpers import (
    notify_lab_techs_order_cancelled,
    notify_lab_techs_order_created,
)
from Services.lab_service import (
    EXTENSION_MEDIA_TYPES,
    _has_report_file,
    _order_patient_fields,
    _report_source,
    _resolve_report_path,
)

# Doctor UI only surfaces these lab order statuses.
DOCTOR_VISIBLE_LAB_STATUSES = frozenset(
    {
        LabTestStatus.ORDERED,
        LabTestStatus.COMPLETED,
        LabTestStatus.CANCELLED,
    }
)


def _parse_doctor_lab_status(status: str) -> LabTestStatus:
    value = (status or "").strip().lower()
    try:
        parsed = LabTestStatus(value)
    except ValueError as exc:
        allowed = ", ".join(sorted(s.value for s in DOCTOR_VISIBLE_LAB_STATUSES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed values: {allowed}",
        ) from exc
    if parsed not in DOCTOR_VISIBLE_LAB_STATUSES:
        allowed = ", ".join(sorted(s.value for s in DOCTOR_VISIBLE_LAB_STATUSES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed values: {allowed}",
        )
    return parsed


def _lab_order_status_value(order: LabTestOrder) -> str:
    return order.status.value if hasattr(order.status, "value") else str(order.status)


def _serialize_lab_test(
    order: LabTestOrder,
    patient: Patient | None = None,
) -> LabTestListResponse:
    return LabTestListResponse(
        id=order.id,
        patient_id=order.patient_id,
        patient_name=order.patient_name,
        patient_uid=order.patient_uhid,
        registration_source=registration_source_value(
            getattr(patient, "registration_source", None)
        ),
        appointment_id=order.appointment_id,
        admission_id=getattr(order, "admission_id", None),
        department_id=order.department_id,
        lab_test_id=order.lab_test_id,
        price=order.price,
        test_name=order.test_name,
        category=order.category,
        priority=order.priority,
        clinical_notes=order.clinical_notes,
        status=_lab_order_status_value(order),
        created_at=order.created_at,
    )


def _serialize_lab_test_response(
    order: LabTestOrder,
    patient: Patient | None = None,
) -> LabTestResponse:
    return LabTestResponse(
        id=order.id,
        appointment_id=order.appointment_id,
        admission_id=getattr(order, "admission_id", None),
        patient_id=order.patient_id,
        patient_name=order.patient_name,
        patient_uid=order.patient_uhid,
        registration_source=registration_source_value(
            getattr(patient, "registration_source", None)
        ),
        doctor_id=order.doctor_id,
        department_id=order.department_id,
        lab_test_id=order.lab_test_id,
        price=order.price,
        test_name=order.test_name,
        category=order.category,
        priority=order.priority,
        clinical_notes=order.clinical_notes,
        status=_lab_order_status_value(order),
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def create_lab_test_service(
    db: Session,
    payload: LabTestCreate,
    doctor_id: int,
    *,
    commit: bool = True,
):
    appointment = None
    admission = None
    patient_id = None
    duplicate_filter = []
    duplicate_detail = "This test has already been ordered for this appointment"

    if payload.admission_id is not None:
        admission = (
            db.query(IpdAdmission)
            .filter(
                IpdAdmission.id == payload.admission_id,
                IpdAdmission.doctor_id == doctor_id,
            )
            .first()
        )
        if not admission:
            raise HTTPException(
                status_code=404,
                detail="IPD admission not found or does not belong to this doctor",
            )
        if str(admission.status or "").strip().lower() != "admitted":
            raise HTTPException(
                status_code=400,
                detail="Cannot order lab tests for a closed admission",
            )
        patient_id = admission.patient_id
        duplicate_filter = [LabTestOrder.admission_id == admission.id]
        duplicate_detail = "This test has already been ordered for this admission"
    else:
        appointment = (
            db.query(Appointment)
            .filter(
                Appointment.id == payload.appointment_id,
                Appointment.doctor_id == doctor_id,
            )
            .first()
        )
        if not appointment:
            raise HTTPException(
                status_code=404,
                detail="Appointment not found or does not belong to this doctor",
            )
        patient_id = appointment.patient_id
        duplicate_filter = [LabTestOrder.appointment_id == appointment.id]

    patient = h.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    test_match = (
        LabTestOrder.lab_test_id == payload.lab_test_id
        if payload.lab_test_id is not None
        else LabTestOrder.test_name == payload.test_name
    )
    existing_test = (
        db.query(LabTestOrder)
        .filter(
            *duplicate_filter,
            test_match,
            LabTestOrder.status != LabTestStatus.CANCELLED,
        )
        .first()
    )
    if existing_test:
        raise HTTPException(
            status_code=400,
            detail=duplicate_detail,
        )

    if payload.lab_test_id is not None:
        catalog_test = resolve_catalog_test(
            db,
            lab_test_id=payload.lab_test_id,
            test_name=payload.test_name,
            department_id=payload.department_id,
        )
        department_id = catalog_test.department_id
    else:
        department_id = resolve_lab_department_id(
            db,
            department_id=payload.department_id,
            category=payload.category,
            test_name=payload.test_name,
        )
        catalog_test = resolve_catalog_test(
            db,
            lab_test_id=None,
            test_name=payload.test_name,
            department_id=department_id,
        )

    lab_test = LabTestOrder(
        appointment_id=appointment.id if appointment else None,
        admission_id=admission.id if admission else None,
        patient_id=patient.id,
        patient_name=h.display_name(patient.first_name, patient.last_name),
        patient_uhid=patient.patient_uid,
        doctor_id=doctor_id,
        department_id=catalog_test.department_id,
        lab_test_id=catalog_test.id,
        test_name=catalog_test.test_name,
        price=catalog_test.price,
        category=payload.category or (
            "Radiology" if (catalog_test.department.code or "").upper() == "RAD"
            else "Laboratory"
        ),
        priority=payload.priority,
        clinical_notes=payload.clinical_notes,
        status=LabTestStatus.ORDERED,
    )
    db.add(lab_test)
    if commit:
        db.commit()
        db.refresh(lab_test)
        notify_lab_techs_order_created(db, lab_test, doctor_id=doctor_id)
    else:
        db.flush()
        db.refresh(lab_test)
    return _serialize_lab_test_response(lab_test, patient)


def get_lab_tests_service(
    db: Session,
    doctor_id: int,
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(LabTestOrder).filter(LabTestOrder.doctor_id == doctor_id)

    if patient_id:
        query = query.filter(LabTestOrder.patient_id == patient_id)

    if patient_uid:
        query = query.filter(
            LabTestOrder.patient_uhid.ilike(
                f"%{patient_uid.strip()}%"
            )
        )

    if status:
        query = query.filter(
            LabTestOrder.status == _parse_doctor_lab_status(status)
        )
    else:
        query = query.filter(LabTestOrder.status.in_(tuple(DOCTOR_VISIBLE_LAB_STATUSES)))

    if search:
        search = search.strip()
        filters = [
            LabTestOrder.patient_name.ilike(f"%{search}%"),
            LabTestOrder.patient_uhid.ilike(f"%{search}%"),
            LabTestOrder.test_name.ilike(f"%{search}%"),
        ]
        if search.isdigit():
            filters.extend([
                LabTestOrder.id == int(search),
                LabTestOrder.patient_id == int(search),
            ])
        query = query.filter(or_(*filters))

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    total = query.count()

    orders = (
        query
        .order_by(LabTestOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    patient_ids = {order.patient_id for order in orders if order.patient_id}
    patients = {
        row.id: row
        for row in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
    } if patient_ids else {}

    items = [
        _serialize_lab_test(order, patients.get(order.patient_id))
        for order in orders
    ]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def update_lab_test_service(
    db: Session,
    test_id: int,
    payload: LabTestUpdate,
    doctor_id: int,
):
    test = (
        db.query(LabTestOrder)
        .filter(LabTestOrder.id == test_id, LabTestOrder.doctor_id == doctor_id)
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Lab test not found")
    if test.status != LabTestStatus.ORDERED:
        raise HTTPException(status_code=400, detail="Only ordered tests can be updated")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    next_category = update_data.get("category", test.category)
    next_test_name = update_data.get("test_name", test.test_name)
    if "department_id" in update_data or "category" in update_data or "test_name" in update_data:
        update_data["department_id"] = resolve_lab_department_id(
            db,
            department_id=update_data.get("department_id"),
            category=next_category,
            test_name=next_test_name,
        )

    for field, value in update_data.items():
        setattr(test, field, value)

    db.commit()
    db.refresh(test)
    patient = h.get_patient(db, test.patient_id)
    return _serialize_lab_test_response(test, patient)


def cancel_lab_test_service(db: Session, test_id: int, doctor_id: int):
    test = (
        db.query(LabTestOrder)
        .filter(LabTestOrder.id == test_id, LabTestOrder.doctor_id == doctor_id)
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Lab test not found")
    if test.status != LabTestStatus.ORDERED:
        raise HTTPException(status_code=400, detail="Only ordered tests can be cancelled")

    test_name = test.test_name
    test.status = LabTestStatus.CANCELLED
    db.commit()
    db.refresh(test)
    notify_lab_techs_order_cancelled(db, test, doctor_id=doctor_id)
    return {
        "message": "Lab test cancelled successfully",
        "order_id": test.id,
        "test_name": test_name,
    }


def _get_doctor_order(
    db: Session,
    test_id: int,
    doctor_id: int,
) -> LabTestOrder:
    order = (
        db.query(LabTestOrder)
        .filter(
            LabTestOrder.id == test_id,
            LabTestOrder.doctor_id == doctor_id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Lab test not found")
    return order


def get_doctor_lab_report_by_test_service(
    db: Session,
    test_id: int,
    doctor_id: int,
):
    order = _get_doctor_order(db=db, test_id=test_id, doctor_id=doctor_id)

    report = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.parameters),
            joinedload(LabResult.uploaded_by_user),
        )
        .filter(LabResult.lab_test_order_id == order.id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not yet available for this lab test",
        )

    uploader_name = " ".join(
        filter(
            None,
            [
                report.uploaded_by_user.first_name,
                report.uploaded_by_user.last_name,
            ],
        )
    )

    parameters = [
        {
            "id": parameter.id,
            "parameter_name": parameter.parameter_name,
            "value": parameter.value,
            "unit": parameter.unit,
            "normal_range": parameter.normal_range,
            "flag": parameter.flag.value if parameter.flag else None,
        }
        for parameter in report.parameters
    ]

    patient = h.get_patient(db, order.patient_id)
    return {
        "report_id": report.id,
        "order_id": order.id,
        "patient_name": order.patient_name,
        **_order_patient_fields(
            order,
            registration_source=registration_source_value(
                getattr(patient, "registration_source", None) if patient else None
            ),
        ),
        "test_name": order.test_name,
        "lab_test_id": order.lab_test_id,
        "price": order.price,
        "category": order.category,
        "department_id": order.department_id,
        "priority": order.priority,
        "order_status": order.status.value,
        "source": _report_source(report),
        "sample_collected_at": report.sample_collected_at,
        "test_performed_at": report.test_performed_at,
        "remarks": report.remarks,
        "file_name": report.file_name,
        "file_type": report.file_type,
        "file_size": report.file_size,
        "uploaded_by_name": uploader_name,
        "uploaded_at": report.created_at,
        "parameters": parameters,
    }


def get_doctor_lab_report_file_by_test_service(
    db: Session,
    test_id: int,
    doctor_id: int,
):
    order = _get_doctor_order(db=db, test_id=test_id, doctor_id=doctor_id)

    report = (
        db.query(LabResult)
        .filter(LabResult.lab_test_order_id == order.id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not yet available for this lab test",
        )
    if not report.report_file:
        raise HTTPException(status_code=404, detail="No file uploaded")

    file_path = _resolve_report_path(report.report_file)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = report.file_type
    if not media_type:
        media_type = EXTENSION_MEDIA_TYPES.get(
            file_path.suffix.lower(),
            "application/octet-stream",
        )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=report.file_name or file_path.name,
    )
