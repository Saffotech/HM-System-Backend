from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import or_, case , func
from sqlalchemy.orm import Session, joinedload
from Models.user import User
from Models.doctor_lab_test_order import (
    LabTestOrder,
    LabTestStatus,
)
from Models.lab_result import (
    LabResult,
    LabResultParameter,
)
from Schemas.lab_schema import (
    LabReportCreate,
)


def get_lab_order(
    db: Session,
    order_id: int,
) -> LabTestOrder:

    order = (
        db.query(LabTestOrder)
        .options(
            joinedload(LabTestOrder.doctor),
            joinedload(LabTestOrder.lab_result),
        )
        .filter(
            LabTestOrder.id == order_id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Lab order not found"
        )

    return order

def get_orders(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(
            LabTestOrder,
            User,
        )
        .join(
            User,
            User.id == LabTestOrder.doctor_id,
        )
    )

    if status:
        query = query.filter(
            LabTestOrder.status == status
        )

    if priority:
        query = query.filter(
            LabTestOrder.priority == priority
        )

    if category:
        query = query.filter(
            LabTestOrder.category == category
        )

    if doctor_id:
        query = query.filter(
            LabTestOrder.doctor_id == doctor_id
        )

    if patient_id:
        query = query.filter(
            LabTestOrder.patient_id == patient_id
        )

    if from_date:
        query = query.filter(
            LabTestOrder.created_at >= from_date
        )

    if to_date:
        query = query.filter(
            LabTestOrder.created_at <= to_date
        )

    if search:
        search = search.strip()

        filters = [
            LabTestOrder.patient_name.ilike(
                f"%{search}%"
            ),
            LabTestOrder.patient_uhid.ilike(
                f"%{search}%"
            ),
            LabTestOrder.test_name.ilike(
                f"%{search}%"
            ),
        ]

        if search.isdigit():
            filters.extend([
                LabTestOrder.id == int(search),
                LabTestOrder.patient_id == int(search),
            ])

        query = query.filter(
            or_(*filters)
        )

    total = query.count()

    rows = (
        query
        .order_by(
            case(
                (
                    LabTestOrder.priority == "Urgent",
                    0,
                ),
                else_=1,
            ),
            LabTestOrder.created_at.asc(),
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(page_size)
        .all()
    )

    items = []

    for order, doctor in rows:

        doctor_name = " ".join(
            filter(
                None,
                [
                    doctor.first_name,
                    doctor.last_name,
                ],
            )
        )

        items.append({
            "id": order.id,
            "appointment_id": order.appointment_id,
            "patient_id": order.patient_id,
            "patient_name": order.patient_name,
            "patient_uhid": order.patient_uhid,
            "doctor_id": doctor.id,
            "doctor_name": doctor_name,
            "test_name": order.test_name,
            "category": order.category,
            "priority": order.priority,
            "clinical_notes": order.clinical_notes,
            "status": order.status.value,
            "created_at": order.created_at,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

def get_order_detail(
    db: Session,
    order_id: int,
):
    order = (
        db.query(LabTestOrder)
        .options(
            joinedload(LabTestOrder.doctor),
            joinedload(LabTestOrder.lab_result),
        )
        .filter(
            LabTestOrder.id == order_id
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Lab order not found",
        )

    doctor_name = " ".join(
        filter(
            None,
            [
                order.doctor.first_name,
                order.doctor.last_name,
            ],
        )
    )

    report = None

    if order.lab_result:
        report = {
            "id": order.lab_result.id,
            "report_file": order.lab_result.report_file,
            "remarks": order.lab_result.remarks,
            "created_at": order.lab_result.created_at,
        }

    return {
        "id": order.id,
        "appointment_id": order.appointment_id,
        "patient_id": order.patient_id,
        "patient_name": order.patient_name,
        "patient_uhid": order.patient_uhid,
        "doctor_id": order.doctor_id,
        "doctor_name": doctor_name,
        "test_name": order.test_name,
        "category": order.category,
        "priority": order.priority,
        "clinical_notes": order.clinical_notes,
        "status": order.status.value,
        "created_at": order.created_at,
        "report": report,
    }

def mark_sample_collected(
    db: Session,
    order_id: int,
):
    order = get_lab_order(
        db=db,
        order_id=order_id,
    )

    if order.status != LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Only ordered tests can be marked as collected",
        )

    order.status = LabTestStatus.SAMPLE_COLLECTED

    db.commit()
    db.refresh(order)

    return {
        "message": "Sample marked as collected",
        "order_id": order.id,
        "status": order.status.value,
    }


def mark_processing(
    db: Session,
    order_id: int,
):
    order = get_lab_order(
        db=db,
        order_id=order_id,
    )

    if order.status != LabTestStatus.SAMPLE_COLLECTED:
        raise HTTPException(
            status_code=400,
            detail="Only collected samples can be processed",
        )

    order.status = LabTestStatus.PROCESSING

    db.commit()
    db.refresh(order)

    return {
        "message": "Test marked as processing",
        "order_id": order.id,
        "status": order.status.value,
    }

def upload_report(
    db: Session,
    order_id: int,
    payload: LabReportCreate,
    current_user_id: int,
):
    order = get_lab_order(
        db=db,
        order_id=order_id,
    )

    if order.status in [
        LabTestStatus.CANCELLED,
        LabTestStatus.COMPLETED,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Report cannot be uploaded for cancelled or completed orders",
        )

    existing_report = (
        db.query(LabResult)
        .filter(
            LabResult.lab_test_order_id == order.id
        )
        .first()
    )

    if existing_report:
        raise HTTPException(
            status_code=400,
            detail="Report already exists for this order",
        )

    if (
        not payload.report_file
        and not payload.parameters
    ):
        raise HTTPException(
            status_code=400,
            detail="Either report file or parameters must be provided",
        )

    report = LabResult(
        lab_test_order_id=order.id,
        uploaded_by=current_user_id,
        sample_collected_at=payload.sample_collected_at,
        test_performed_at=payload.test_performed_at,
        report_file=payload.report_file,
        remarks=payload.remarks,
    )

    db.add(report)
    db.flush()

    parameter_objects = []

    for parameter in payload.parameters:

        parameter_objects.append(
            LabResultParameter(
                lab_result_id=report.id,
                parameter_name=parameter.parameter_name,
                value=parameter.value,
                unit=parameter.unit,
                normal_range=parameter.normal_range,
                flag=parameter.flag,
            )
        )

    if parameter_objects:
        db.add_all(parameter_objects)

    order.status = LabTestStatus.COMPLETED

    db.commit()
    db.refresh(report)

    return {
        "message": "Report uploaded successfully",
        "report_id": report.id,
        "order_id": order.id,
        "status": order.status.value,
    }


def get_reports(
    db: Session,
    search: str | None = None,
    patient_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.uploaded_by_user),
        )
    )

    # Join only when needed
    if patient_id or search:
        query = query.join(
            LabTestOrder,
            LabTestOrder.id == LabResult.lab_test_order_id,
        )

    if from_date:
        query = query.filter(
            LabResult.created_at >= from_date
        )

    if to_date:
        query = query.filter(
            LabResult.created_at <= to_date
        )

    if patient_id:
        query = query.filter(
            LabTestOrder.patient_id == patient_id
        )

    if search:
        search = search.strip()

        query = query.filter(
            or_(
                LabTestOrder.patient_name.ilike(
                    f"%{search}%"
                ),
                LabTestOrder.patient_uhid.ilike(
                    f"%{search}%"
                ),
                LabTestOrder.test_name.ilike(
                    f"%{search}%"
                ),
            )
        )

    total = query.count()

    reports = (
        query
        .order_by(
            LabResult.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
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

        items.append({
            "report_id": report.id,
            "order_id": report.lab_test_order_id,
            "patient_name": report.lab_order.patient_name,
            "patient_uhid": report.lab_order.patient_uhid,
            "test_name": report.lab_order.test_name,
            "uploaded_by": report.uploaded_by,
            "uploaded_by_name": uploader_name,
            "report_file": report.report_file,
            "uploaded_at": report.created_at,
            "status": report.lab_order.status.value,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }

def get_report_detail(
    db: Session,
    report_id: int,
):
    report = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.parameters),
            joinedload(LabResult.uploaded_by_user),
        )
        .filter(
            LabResult.id == report_id
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
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

    parameters = []

    for parameter in report.parameters:
        parameters.append({
            "id": parameter.id,
            "parameter_name": parameter.parameter_name,
            "value": parameter.value,
            "unit": parameter.unit,
            "normal_range": parameter.normal_range,
            "flag": parameter.flag.value if parameter.flag else None,
        })

    return {
        "id": report.id,
        "lab_test_order_id": report.lab_test_order_id,
        "uploaded_by": report.uploaded_by,
        "uploaded_by_name": uploader_name,
        "sample_collected_at": report.sample_collected_at,
        "test_performed_at": report.test_performed_at,
        "report_file": report.report_file,
        "remarks": report.remarks,
        "created_at": report.created_at,
        "order": {
            "id": report.lab_order.id,
            "patient_id": report.lab_order.patient_id,
            "patient_name": report.lab_order.patient_name,
            "patient_uhid": report.lab_order.patient_uhid,
            "doctor_id": report.lab_order.doctor_id,
            "test_name": report.lab_order.test_name,
            "category": report.lab_order.category,
            "priority": report.lab_order.priority,
            "status": report.lab_order.status.value,
        },
        "parameters": parameters,
    }

def get_dashboard_stats(
    db: Session,
):
    ist_now = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    today = ist_now.date()

    total_today = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            func.date(
                LabTestOrder.created_at
            ) == today
        )
        .scalar()
    )

    pending = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            LabTestOrder.status == LabTestStatus.ORDERED
        )
        .scalar()
    )

    sample_collected = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            LabTestOrder.status
            == LabTestStatus.SAMPLE_COLLECTED
        )
        .scalar()
    )

    processing = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            LabTestOrder.status
            == LabTestStatus.PROCESSING
        )
        .scalar()
    )

    completed_today = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            LabTestOrder.status
            == LabTestStatus.COMPLETED,
            func.date(
                LabTestOrder.updated_at
            ) == today,
        )
        .scalar()
    )

    urgent_pending = (
        db.query(
            func.count(LabTestOrder.id)
        )
        .filter(
            LabTestOrder.priority.ilike(
                "Urgent"
            ),
            LabTestOrder.status.in_([
                LabTestStatus.ORDERED,
                LabTestStatus.SAMPLE_COLLECTED,
                LabTestStatus.PROCESSING,
            ]),
        )
        .scalar()
    )

    return {
        "total_today": total_today or 0,
        "pending": pending or 0,
        "sample_collected": sample_collected or 0,
        "processing": processing or 0,
        "completed_today": completed_today or 0,
        "urgent_pending": urgent_pending or 0,
    }

