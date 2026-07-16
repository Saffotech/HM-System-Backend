from datetime import date

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from Models.doctor_lab_test_order import LabTestOrder, LabTestStatus
from Models.lab_result import LabResult
from Models.opd_billing import Appointment
from Schemas.doctor_lab_test_schema import (
    LabTestCreate,
    LabTestUpdate,
    LabTestListResponse,
    LabTestResponse,
)
from Schemas.lab_schema import ReportSource
from Services import doctor_helpers as h
from Services.lab_notification_helpers import (
    notify_lab_order_cancelled,
    notify_lab_order_created,
)
from Services.lab_service import (
    EXTENSION_MEDIA_TYPES,
    _apply_report_source_filter,
    _end_of_day,
    _has_report_file,
    _order_patient_fields,
    _parse_lab_status,
    _report_source,
    _resolve_report_path,
)


def _serialize_lab_test(order: LabTestOrder) -> LabTestListResponse:
    return LabTestListResponse.model_validate(order)


def _serialize_lab_test_response(order: LabTestOrder) -> LabTestResponse:
    return LabTestResponse.model_validate(order)


def create_lab_test_service(db: Session, payload: LabTestCreate, doctor_id: int):
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

    patient = h.get_patient(db, appointment.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing_test = (
        db.query(LabTestOrder)
        .filter(
            LabTestOrder.appointment_id == payload.appointment_id,
            LabTestOrder.test_name == payload.test_name,
            LabTestOrder.status != LabTestStatus.CANCELLED,
        )
        .first()
    )
    if existing_test:
        raise HTTPException(
            status_code=400,
            detail="This test has already been ordered for this appointment",
        )

    lab_test = LabTestOrder(
        appointment_id=appointment.id,
        patient_id=patient.id,
        patient_name=h.display_name(patient.first_name, patient.last_name),
        patient_uhid=patient.patient_uid,
        doctor_id=doctor_id,
        test_name=payload.test_name,
        category=payload.category.value,
        priority=payload.priority,
        clinical_notes=payload.clinical_notes,
        status=LabTestStatus.ORDERED,
    )
    db.add(lab_test)
    db.commit()
    db.refresh(lab_test)
    notify_lab_order_created(db, lab_test, doctor_id)
    return _serialize_lab_test_response(lab_test)


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
            LabTestOrder.status == _parse_lab_status(status)
        )

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

    items = [
        _serialize_lab_test(order)
        for order in (
            query
            .order_by(LabTestOrder.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    ]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_lab_test_by_id_service(
    db: Session,
    test_id: int,
    doctor_id: int,
):
    order = (
        db.query(LabTestOrder)
        .options(
            joinedload(LabTestOrder.lab_result).selectinload(
                LabResult.parameters
            ),
        )
        .filter(
            LabTestOrder.id == test_id,
            LabTestOrder.doctor_id == doctor_id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Lab test not found")

    report = None
    report_uploaded = False
    has_report = False

    if order.lab_result:
        has_report = True
        report_uploaded = _has_report_file(order.lab_result)
        report = {
            "id": order.lab_result.id,
            "report_file": order.lab_result.report_file,
            "remarks": order.lab_result.remarks,
            "created_at": order.lab_result.created_at,
            "file_name": order.lab_result.file_name,
            "file_type": order.lab_result.file_type,
            "file_size": order.lab_result.file_size,
            "source": _report_source(order.lab_result),
        }

    return {
        "id": order.id,
        "appointment_id": order.appointment_id,
        "patient_name": order.patient_name,
        **_order_patient_fields(order),
        "doctor_id": order.doctor_id,
        "test_name": order.test_name,
        "category": order.category,
        "priority": order.priority,
        "clinical_notes": order.clinical_notes,
        "status": order.status.value,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "report_uploaded": report_uploaded,
        "has_report": has_report,
        "report": report,
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

    for field, value in update_data.items():
        if field == "category" and value is not None:
            value = value.value
        setattr(test, field, value)

    db.commit()
    db.refresh(test)
    return _serialize_lab_test_response(test)


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

    test.status = LabTestStatus.CANCELLED
    db.commit()
    db.refresh(test)
    notify_lab_order_cancelled(db, test, doctor_id)
    return {"message": "Lab test cancelled successfully"}


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


def get_doctor_lab_reports_service(
    db: Session,
    doctor_id: int,
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    patient_name: str | None = None,
    test_name: str | None = None,
    status: str | None = None,
    source: ReportSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(LabResult)
        .join(
            LabTestOrder,
            LabTestOrder.id == LabResult.lab_test_order_id,
        )
        .filter(LabTestOrder.doctor_id == doctor_id)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.uploaded_by_user),
            selectinload(LabResult.parameters),
        )
    )

    if from_date:
        query = query.filter(LabResult.created_at >= from_date)

    if to_date:
        query = query.filter(LabResult.created_at <= _end_of_day(to_date))

    if patient_id:
        query = query.filter(LabTestOrder.patient_id == patient_id)

    if patient_uid:
        query = query.filter(
            LabTestOrder.patient_uhid.ilike(
                f"%{patient_uid.strip()}%"
            )
        )

    if patient_name:
        query = query.filter(
            LabTestOrder.patient_name.ilike(
                f"%{patient_name.strip()}%"
            )
        )

    if test_name:
        query = query.filter(
            LabTestOrder.test_name.ilike(f"%{test_name.strip()}%")
        )

    if status:
        query = query.filter(
            LabTestOrder.status == _parse_lab_status(status)
        )

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

    if source:
        query = _apply_report_source_filter(query, source)

    total = query.count()

    reports = (
        query
        .order_by(LabResult.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for report in reports:
        uploader_name = " ".join(
            filter(
                None,
                [
                    report.uploaded_by_user.first_name,
                    report.uploaded_by_user.last_name,
                ],
            )
        )
        order = report.lab_order
        items.append({
            "report_id": report.id,
            "order_id": order.id,
            "patient_name": order.patient_name,
            **_order_patient_fields(order),
            "test_name": order.test_name,
            "category": order.category,
            "status": order.status.value,
            "source": _report_source(report),
            "has_file": _has_report_file(report),
            "uploaded_at": report.created_at,
            "uploaded_by_name": uploader_name,
        })

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


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

    return {
        "report_id": report.id,
        "order_id": order.id,
        "patient_name": order.patient_name,
        **_order_patient_fields(order),
        "test_name": order.test_name,
        "category": order.category,
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
