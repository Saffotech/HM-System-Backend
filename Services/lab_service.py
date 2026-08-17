import logging
import os
import shutil
import uuid
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import case, exists, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from Enums.notification import NotificationType, ReferenceType, SourceModule
from Models.doctor_lab_test_order import LabTestOrder, LabTestStatus
from Models.lab_result import LabResult, LabResultParameter, ParameterFlag
from Models.patient import Patient, registration_source_value
from Models.user import User
from Schemas.lab_schema import LabReportCreate, ReportSource
from Services import opd_helpers as h
from Services.lab_department_helpers import (
    assert_order_accessible_by_lab_tech,
    filter_orders_for_lab_tech,
    require_lab_tech_department_id,
)
from Services.notification_service import create_notification

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
EXTENSION_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _lab_uploader_name(db: Session, user_id: int) -> str:
    uploader = db.query(User).filter(User.id == user_id).first()
    if not uploader:
        return "Lab Technician"
    return h.display_name(uploader.first_name, uploader.last_name)


def _notify_doctor_lab_report(
    db: Session,
    order: LabTestOrder,
    *,
    current_user_id: int,
) -> None:
    create_notification(
        db,
        user_id=order.doctor_id,
        title="Lab Report Ready",
        message=f"{order.test_name} — {order.patient_name}",
        notification_type=NotificationType.LAB_REPORT_READY,
        source_module=SourceModule.LAB,
        reference_type=ReferenceType.LAB_ORDER,
        reference_id=order.id,
        created_by=current_user_id,
        created_by_name=_lab_uploader_name(db, current_user_id),
    )


def format_file_size(size_in_bytes: int) -> str:
    if not size_in_bytes:
        return "0 B"

    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"

    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"

    return f"{size_in_bytes / (1024 * 1024):.1f} MB"

def _order_patient_fields(
    order: LabTestOrder,
    *,
    registration_source: str | None = None,
) -> dict:
    """Lab orders snapshot patient UID on the order row."""
    return {
        "patient_id": order.patient_id,
        "patient_uid": order.patient_uhid,
        "registration_source": registration_source_value(registration_source),
    }


def _registration_sources_by_patient_id(
    db: Session,
    patient_ids: list[int] | set[int],
) -> dict[int, str]:
    ids = {int(pid) for pid in patient_ids if pid}
    if not ids:
        return {}
    rows = (
        db.query(Patient.id, Patient.registration_source)
        .filter(Patient.id.in_(ids))
        .all()
    )
    return {pid: registration_source_value(source) for pid, source in rows}


def _get_upload_dir() -> Path:
    upload_dir = Path(
        os.getenv("LAB_UPLOAD_DIR", "uploads/lab_reports")
    )
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _stored_report_path(filename: str) -> str:
    absolute = (_get_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def _resolve_report_path(stored_path: str) -> Path:
    upload_dir = _get_upload_dir().resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if upload_dir not in candidate.parents and candidate != upload_dir:
        raise HTTPException(
            status_code=400,
            detail="Invalid report file path",
        )
    return candidate


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=IST)


def _parse_lab_status(status: str) -> LabTestStatus:
    # Legacy FE filter key — Option B folded "processing" into sample_collected.
    if status == "processing":
        return LabTestStatus.SAMPLE_COLLECTED
    try:
        return LabTestStatus(status)
    except ValueError as exc:
        valid = ", ".join(s.value for s in LabTestStatus)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Allowed values: {valid}",
        ) from exc


def _parse_parameter_flag(flag: str | None) -> ParameterFlag | None:
    if flag is None:
        return None
    try:
        return ParameterFlag(flag)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid parameter flag. Allowed values: normal, low, high",
        ) from exc


def _has_report_file(report: LabResult) -> bool:
    return bool(report.report_file and report.report_file.strip())


def _has_parameters(report: LabResult) -> bool:
    return bool(report.parameters)


def _report_ready_for_completion(report: LabResult | None) -> bool:
    """Option B: complete only when parameters and/or a report file exist."""
    if report is None:
        return False
    return _has_report_file(report) or _has_parameters(report)


def _get_order_report(db: Session, order_id: int) -> LabResult | None:
    return (
        db.query(LabResult)
        .options(selectinload(LabResult.parameters))
        .filter(LabResult.lab_test_order_id == order_id)
        .first()
    )


def _report_source(report: LabResult) -> str:
    has_file = _has_report_file(report)
    has_params = _has_parameters(report)
    if has_params and has_file:
        return ReportSource.BOTH.value
    if has_params:
        return ReportSource.PARAMETERS.value
    if has_file:
        return ReportSource.PDF.value
    return "NONE"
 

def _apply_report_source_filter(query, source: ReportSource):
    has_parameters = exists().where(
        LabResultParameter.lab_result_id == LabResult.id
    )
    has_file = LabResult.report_file.isnot(None)
    has_nonempty_file = LabResult.report_file != ""

    if source == ReportSource.PARAMETERS:
        return query.filter(has_parameters, or_(~has_file, LabResult.report_file == ""))
    if source == ReportSource.PDF:
        return query.filter(has_nonempty_file, ~has_parameters)
    if source == ReportSource.BOTH:
        return query.filter(has_parameters, has_nonempty_file)
    return query


def get_lab_order(
    db: Session,
    order_id: int,
    current_user: User | None = None,
) -> LabTestOrder:
    order = (
        db.query(LabTestOrder)
        .options(
            joinedload(LabTestOrder.doctor),
            joinedload(LabTestOrder.lab_result),
        )
        .filter(LabTestOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    if current_user is not None:
        assert_order_accessible_by_lab_tech(order, current_user)
    return order


def get_orders(
    db: Session,
    current_user: User,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(LabTestOrder, User)
        .join(User, User.id == LabTestOrder.doctor_id)
    )
    query = filter_orders_for_lab_tech(query, current_user)

    if status:
        query = query.filter(
            LabTestOrder.status == _parse_lab_status(status)
        )

    if priority:
        query = query.filter(LabTestOrder.priority == priority)

    if category:
        query = query.filter(LabTestOrder.category == category)

    if doctor_id:
        query = query.filter(LabTestOrder.doctor_id == doctor_id)

    if patient_id:
        query = query.filter(LabTestOrder.patient_id == patient_id)

    if patient_uid:
        query = query.filter(
            LabTestOrder.patient_uhid.ilike(
                f"%{patient_uid.strip()}%"
            )
        )

    if from_date:
        query = query.filter(LabTestOrder.created_at >= from_date)

    if to_date:
        query = query.filter(LabTestOrder.created_at <= _end_of_day(to_date))

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

    total = query.count()

    rows = (
        query
        .order_by(
            case((LabTestOrder.priority == "Urgent", 0), else_=1),
            LabTestOrder.created_at.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    source_by_patient = _registration_sources_by_patient_id(
        db,
        [order.patient_id for order, _doctor in rows],
    )
    for order, doctor in rows:
        doctor_name = " ".join(
            filter(None, [doctor.first_name, doctor.last_name])
        )
        items.append({
            "id": order.id,
            "appointment_id": order.appointment_id,
            "patient_name": order.patient_name,
            **_order_patient_fields(
                order,
                registration_source=source_by_patient.get(order.patient_id),
            ),
            "doctor_id": doctor.id,
            "doctor_name": doctor_name,
            "department_id": order.department_id,
            "test_name": order.test_name,
            "category": order.category,
            "priority": order.priority,
            "clinical_notes": order.clinical_notes,
            "status": order.status.value,
            "created_at": order.created_at,
        })

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_order_detail(db: Session, order_id: int, current_user: User):
    order = (
        db.query(LabTestOrder)
        .options(
            joinedload(LabTestOrder.doctor),
            joinedload(LabTestOrder.lab_result).selectinload(
                LabResult.parameters
            ),
        )
        .filter(LabTestOrder.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    assert_order_accessible_by_lab_tech(order, current_user)

    doctor_name = " ".join(
        filter(None, [order.doctor.first_name, order.doctor.last_name])
    )

    report = None
    report_uploaded = False

    if order.lab_result:
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
        **_order_patient_fields(
            order,
            registration_source=_registration_sources_by_patient_id(
                db, [order.patient_id]
            ).get(order.patient_id),
        ),
        "doctor_id": order.doctor_id,
        "doctor_name": doctor_name,
        "department_id": order.department_id,
        "test_name": order.test_name,
        "category": order.category,
        "priority": order.priority,
        "clinical_notes": order.clinical_notes,
        "status": order.status.value,
        "created_at": order.created_at,
        "report_uploaded": report_uploaded,
        "report": report,
    }


def mark_sample_collected(db: Session, order_id: int, current_user: User):
    order = get_lab_order(db=db, order_id=order_id, current_user=current_user)

    if order.status == LabTestStatus.SAMPLE_COLLECTED:
        return {
            "message": "Sample already marked as collected",
            "order_id": order.id,
            "status": order.status.value,
        }

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


def mark_processing(db: Session, order_id: int, current_user: User):
    """Deprecated no-op for Option B (processing status removed).

    Kept so existing clients that still PATCH .../processing do not break.
    Sample must already be collected; status stays sample_collected.
    """
    order = get_lab_order(db=db, order_id=order_id, current_user=current_user)

    if order.status == LabTestStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Cancelled tests cannot be processed",
        )

    if order.status == LabTestStatus.COMPLETED:
        return {
            "message": "Test already completed",
            "order_id": order.id,
            "status": order.status.value,
        }

    if order.status == LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Collect the sample before continuing",
        )

    if order.status != LabTestStatus.SAMPLE_COLLECTED:
        raise HTTPException(
            status_code=400,
            detail="Only collected samples can continue to reporting",
        )

    return {
        "message": "Ready for report — upload parameters and/or file, then complete",
        "order_id": order.id,
        "status": order.status.value,
    }


def mark_completed(db: Session, order_id: int, current_user: User):
    """Option B: sample_collected → completed when report has params and/or file."""
    order = get_lab_order(db=db, order_id=order_id, current_user=current_user)

    if order.status == LabTestStatus.COMPLETED:
        return {
            "message": "Test already completed",
            "order_id": order.id,
            "status": order.status.value,
        }

    if order.status == LabTestStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Cancelled tests cannot be completed",
        )

    if order.status != LabTestStatus.SAMPLE_COLLECTED:
        raise HTTPException(
            status_code=400,
            detail="Only sample-collected tests can be completed",
        )

    report = _get_order_report(db, order.id)
    if not _report_ready_for_completion(report):
        raise HTTPException(
            status_code=400,
            detail=(
                "Upload report parameters and/or a report file "
                "before completing the test"
            ),
        )

    order.status = LabTestStatus.COMPLETED
    db.commit()
    db.refresh(order)

    return {
        "message": "Test completed successfully",
        "order_id": order.id,
        "status": order.status.value,
    }


def upload_report(
    db: Session,
    order_id: int,
    payload: LabReportCreate,
    current_user_id: int,
    current_user: User,
):
    order = get_lab_order(db=db, order_id=order_id, current_user=current_user)

    if order.status == LabTestStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Report cannot be uploaded for cancelled orders",
        )

    if order.status == LabTestStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Report already finalized for this completed order",
        )

    if order.status == LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Collect the sample before uploading a report",
        )

    if order.status != LabTestStatus.SAMPLE_COLLECTED:
        raise HTTPException(
            status_code=400,
            detail="Report can only be uploaded for sample-collected orders",
        )

    existing_report = (
        db.query(LabResult)
        .filter(LabResult.lab_test_order_id == order.id)
        .first()
    )
    if existing_report:
        raise HTTPException(
            status_code=400,
            detail="Report already exists for this order",
        )

    if not payload.report_file and not payload.parameters:
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

    try:
        db.add(report)
        db.flush()

        parameter_objects = [
            LabResultParameter(
                lab_result_id=report.id,
                parameter_name=parameter.parameter_name,
                value=parameter.value,
                unit=parameter.unit,
                normal_range=parameter.normal_range,
                flag=_parse_parameter_flag(parameter.flag),
            )
            for parameter in payload.parameters
        ]

        if parameter_objects:
            db.add_all(parameter_objects)

        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    _notify_doctor_lab_report(
        db,
        order,
        current_user_id=current_user_id,
    )

    return {
        "message": "Report uploaded successfully",
        "report_id": report.id,
        "order_id": order.id,
        "status": order.status.value,
    }


def upload_report_file(
    db: Session,
    order_id: int,
    file: UploadFile,
    current_user_id: int,
    current_user: User,
):
    order = get_lab_order(db=db, order_id=order_id, current_user=current_user)

    if order.status == LabTestStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Report cannot be uploaded for cancelled orders",
        )

    if order.status == LabTestStatus.ORDERED:
        raise HTTPException(
            status_code=400,
            detail="Collect the sample before uploading a report file",
        )

    # Option B: attach file while sample_collected (before complete) or after completed.
    if order.status not in (
        LabTestStatus.SAMPLE_COLLECTED,
        LabTestStatus.COMPLETED,
    ):
        raise HTTPException(
            status_code=400,
            detail="Report file can only be uploaded for sample-collected or completed orders",
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must include a filename",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG and PNG files are allowed",
        )

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 10 MB",
        )

    report = (
        db.query(LabResult)
        .filter(LabResult.lab_test_order_id == order.id)
        .first()
    )

    report_created_here = False
    if not report:
        report = LabResult(
            lab_test_order_id=order.id,
            uploaded_by=current_user_id,
            sample_collected_at=None,
            test_performed_at=None,
        )
        db.add(report)
        db.flush()
        report_created_here = True

    had_previous_file = bool(report.report_file)
    old_file_path = None
    if report.report_file:
        try:
            old_file_path = _resolve_report_path(report.report_file)
        except HTTPException:
            old_file_path = None

    unique_name = f"{uuid.uuid4()}{extension}"
    stored_path = _stored_report_path(unique_name)
    upload_dir = _get_upload_dir()
    absolute_path = upload_dir / unique_name

    try:
        with open(absolute_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        logger.exception("Failed to save lab report file for order %s", order_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to save file",
        ) from exc

    report.report_file = stored_path
    report.file_name = file.filename
    report.file_type = file.content_type or EXTENSION_MEDIA_TYPES.get(extension)
    report.file_size = file_size
    report.uploaded_by = current_user_id

    try:
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        if absolute_path.exists():
            try:
                absolute_path.unlink()
            except OSError:
                logger.warning(
                    "Could not remove orphaned lab file %s", absolute_path
                )
        raise

    if old_file_path and old_file_path.exists():
        try:
            old_file_path.unlink()
        except OSError:
            logger.warning("Could not remove old lab file %s", old_file_path)

    if report_created_here:
        _notify_doctor_lab_report(
            db,
            order,
            current_user_id=current_user_id,
        )

    return {
        "message": "Report generated successfully",
        "report_id": report.id,
        "order_id": order.id,
        "file_name": report.file_name,
        "file_type": report.file_type,
        "file_size": report.file_size,
        "file_size_display": format_file_size(report.file_size),
    }


def get_reports(
    db: Session,
    current_user: User,
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    patient_name: str | None = None,
    test_name: str | None = None,
    source: ReportSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    tech_dept_id = require_lab_tech_department_id(current_user)

    query = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.uploaded_by_user),
            selectinload(LabResult.parameters),
        )
        .join(
            LabTestOrder,
            LabTestOrder.id == LabResult.lab_test_order_id,
        )
        .filter(LabTestOrder.department_id == tech_dept_id)
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
            LabTestOrder.patient_name.ilike(f"%{patient_name.strip()}%")
        )

    if test_name:
        query = query.filter(
            LabTestOrder.test_name.ilike(f"%{test_name.strip()}%")
        )

    if search:
        search = search.strip()
        query = query.filter(
            or_(
                LabTestOrder.patient_name.ilike(f"%{search}%"),
                LabTestOrder.patient_uhid.ilike(f"%{search}%"),
                LabTestOrder.test_name.ilike(f"%{search}%"),
            )
        )

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

    doctor_ids = {
        report.lab_order.doctor_id
        for report in reports
        if report.lab_order and report.lab_order.doctor_id
    }
    doctors = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(doctor_ids)).all()
    } if doctor_ids else {}

    source_by_patient = _registration_sources_by_patient_id(
        db,
        [
            report.lab_order.patient_id
            for report in reports
            if report.lab_order
        ],
    )

    items = []
    for report in reports:
        uploader_name = " ".join(
            filter(
                None,
                [
                    report.uploaded_by_user.first_name if report.uploaded_by_user else None,
                    report.uploaded_by_user.last_name if report.uploaded_by_user else None,
                ],
            )
        ) or None
        doctor = doctors.get(report.lab_order.doctor_id) if report.lab_order else None
        doctor_name = (
            h.display_name(doctor.first_name, doctor.last_name) if doctor else None
        )
        items.append({
            "report_id": report.id,
            "order_id": report.lab_test_order_id,
            "patient_name": report.lab_order.patient_name,
            **_order_patient_fields(
                report.lab_order,
                registration_source=source_by_patient.get(report.lab_order.patient_id),
            ),
            "doctor_id": report.lab_order.doctor_id if report.lab_order else None,
            "doctor_name": doctor_name,
            "test_name": report.lab_order.test_name,
            "uploaded_by": report.uploaded_by,
            "uploaded_by_name": uploader_name,
            "report_file": report.report_file,
            "uploaded_at": report.created_at,
            "status": report.lab_order.status.value,
            "source": _report_source(report),
        })

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_report_detail(db: Session, report_id: int, current_user: User):
    report = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.parameters),
            joinedload(LabResult.uploaded_by_user),
        )
        .filter(LabResult.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.lab_order:
        raise HTTPException(status_code=404, detail="Report not found")
    assert_order_accessible_by_lab_tech(report.lab_order, current_user)

    uploader_name = " ".join(
        filter(
            None,
            [
                report.uploaded_by_user.first_name,
                report.uploaded_by_user.last_name,
            ],
        )
    )

    doctor = (
        db.query(User).filter(User.id == report.lab_order.doctor_id).first()
        if report.lab_order and report.lab_order.doctor_id
        else None
    )
    doctor_name = h.display_name(
        doctor.first_name,
        doctor.last_name,
        prefix="Dr. ",
    ) if doctor else ""

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
        "id": report.id,
        "lab_test_order_id": report.lab_test_order_id,
        "uploaded_by": report.uploaded_by,
        "uploaded_by_name": uploader_name,
        "sample_collected_at": report.sample_collected_at,
        "test_performed_at": report.test_performed_at,
        "report_file": report.report_file,
        "remarks": report.remarks,
        "created_at": report.created_at,
        "file_name": report.file_name,
        "file_type": report.file_type,
        "file_size": report.file_size,
        "file_size_display": format_file_size(report.file_size),
        "source": _report_source(report),
        "order": {
            "id": report.lab_order.id,
            "patient_name": report.lab_order.patient_name,
            **_order_patient_fields(
                report.lab_order,
                registration_source=_registration_sources_by_patient_id(
                    db, [report.lab_order.patient_id]
                ).get(report.lab_order.patient_id),
            ),
            "doctor_id": report.lab_order.doctor_id,
            "doctor_name": doctor_name,
            "department_id": report.lab_order.department_id,
            "test_name": report.lab_order.test_name,
            "category": report.lab_order.category,
            "priority": report.lab_order.priority,
            "status": report.lab_order.status.value,
        },
        "parameters": parameters,
    }


def get_dashboard_stats(db: Session, current_user: User):
    ist_now = datetime.now(IST)
    today = ist_now.date()
    tech_dept_id = require_lab_tech_department_id(current_user)
    dept_filter = LabTestOrder.department_id == tech_dept_id

    total_today = (
        db.query(func.count(LabTestOrder.id))
        .filter(
            dept_filter,
            func.date(LabTestOrder.created_at) == today,
        )
        .scalar()
    )

    pending = (
        db.query(func.count(LabTestOrder.id))
        .filter(
            dept_filter,
            LabTestOrder.status == LabTestStatus.ORDERED,
        )
        .scalar()
    )

    sample_collected = (
        db.query(func.count(LabTestOrder.id))
        .filter(
            dept_filter,
            LabTestOrder.status == LabTestStatus.SAMPLE_COLLECTED,
        )
        .scalar()
    )

    completed_today = (
        db.query(func.count(LabTestOrder.id))
        .filter(
            dept_filter,
            LabTestOrder.status == LabTestStatus.COMPLETED,
            func.date(LabTestOrder.updated_at) == today,
        )
        .scalar()
    )

    urgent_pending = (
        db.query(func.count(LabTestOrder.id))
        .filter(
            dept_filter,
            LabTestOrder.priority.ilike("Urgent"),
            LabTestOrder.status.in_([
                LabTestStatus.ORDERED,
                LabTestStatus.SAMPLE_COLLECTED,
            ]),
        )
        .scalar()
    )

    return {
        "total_today": total_today or 0,
        "pending": pending or 0,
        "sample_collected": sample_collected or 0,
        # Deprecated under Option B — kept as 0 for existing dashboard clients.
        "processing": 0,
        "completed_today": completed_today or 0,
        "urgent_pending": urgent_pending or 0,
    }


def get_report_file(db: Session, report_id: int, current_user: User):
    report = (
        db.query(LabResult)
        .options(joinedload(LabResult.lab_order))
        .filter(LabResult.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.lab_order:
        raise HTTPException(status_code=404, detail="Report not found")
    assert_order_accessible_by_lab_tech(report.lab_order, current_user)

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
