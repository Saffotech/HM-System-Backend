"""Read-only lab reports for nurses, scoped to occupied (optionally allocated) beds."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from Models.doctor_lab_test_order import LabTestOrder
from Models.lab_result import LabResult
from Models.opd_billing import Bed
from Models.user import User
from Services.ipd_helpers import doctor_name_map
from Services.lab_service import (
    EXTENSION_MEDIA_TYPES,
    _active_admissions_by_patient_id,
    _end_of_day,
    _order_patient_fields,
    _registration_sources_by_patient_id,
    _report_source,
    _resolve_report_path,
    format_file_size,
)

IST = ZoneInfo("Asia/Kolkata")


def _occupied_beds_by_patient_id(db: Session) -> dict[int, Bed]:
    beds = (
        db.query(Bed)
        .filter(
            Bed.status == "occupied",
            Bed.patient_id.isnot(None),
        )
        .order_by(Bed.admitted_at.desc())
        .all()
    )
    by_patient: dict[int, Bed] = {}
    for bed in beds:
        if bed.patient_id not in by_patient:
            by_patient[bed.patient_id] = bed
    return by_patient


def _allowed_patient_ids(
    db: Session,
    *,
    allocated_only: bool,
    nurse_id: int | None,
    assignment_date=None,
    shift_name: str | None = None,
) -> list[int]:
    if allocated_only:
        if nurse_id is None:
            return []
        from Services.nurse_shift_bed_allocation_service import (
            get_allocated_patient_ids_for_nurse,
        )

        return get_allocated_patient_ids_for_nurse(
            db,
            nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        )
    return list(_occupied_beds_by_patient_id(db).keys())


def _assert_patient_in_scope(
    db: Session,
    patient_id: int | None,
    *,
    allocated_only: bool,
    nurse_id: int | None,
    assignment_date=None,
    shift_name: str | None = None,
) -> None:
    if not patient_id:
        raise HTTPException(status_code=404, detail="Report not found")
    allowed = set(
        _allowed_patient_ids(
            db,
            allocated_only=allocated_only,
            nurse_id=nurse_id,
            assignment_date=assignment_date,
            shift_name=shift_name,
        )
    )
    if patient_id not in allowed:
        raise HTTPException(status_code=404, detail="Report not found")


def _uploader_name(user: User | None) -> str | None:
    if not user:
        return None
    return " ".join(filter(None, [user.first_name, user.last_name])) or None


def _visit_location_from_bed(bed: Bed | None, admission_fields: dict) -> dict:
    if bed is None:
        return admission_fields
    fields = dict(admission_fields)
    fields["encounter_type"] = "IPD"
    fields["ward_name"] = bed.ward_name
    fields["bed_number"] = bed.bed_number
    return fields


def _serialize_list_item(
    report: LabResult,
    *,
    doctor_name: str | None,
    registration_source: str | None,
    admission,
    bed: Bed | None,
) -> dict:
    order = report.lab_order
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    patient_fields = _visit_location_from_bed(
        bed,
        _order_patient_fields(
            order,
            registration_source=registration_source,
            admission=admission,
            include_visit_location=True,
        ),
    )
    return {
        "report_id": report.id,
        "order_id": report.lab_test_order_id,
        "patient_name": order.patient_name,
        **patient_fields,
        "doctor_id": order.doctor_id,
        "doctor_name": doctor_name,
        "test_name": order.test_name,
        "uploaded_by": report.uploaded_by,
        "uploaded_by_name": _uploader_name(report.uploaded_by_user),
        "report_file": report.report_file,
        "uploaded_at": report.created_at,
        "status": status,
        "source": _report_source(report),
    }


def list_nurse_lab_reports_service(
    db: Session,
    *,
    nurse_id: int,
    search: str | None = None,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    patient_name: str | None = None,
    test_name: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    allocated_only: bool = False,
    assignment_date=None,
    shift_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    allowed_ids = _allowed_patient_ids(
        db,
        allocated_only=allocated_only,
        nurse_id=nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    if patient_id:
        allowed_ids = [pid for pid in allowed_ids if pid == patient_id]

    if not allowed_ids:
        return {
            "success": True,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "items": [],
        }

    query = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.lab_order),
            joinedload(LabResult.uploaded_by_user),
            selectinload(LabResult.parameters),
        )
        .join(LabTestOrder, LabTestOrder.id == LabResult.lab_test_order_id)
        .filter(LabTestOrder.patient_id.in_(allowed_ids))
    )

    if from_date:
        query = query.filter(LabResult.created_at >= datetime.combine(from_date, time.min, tzinfo=IST))

    if to_date:
        query = query.filter(LabResult.created_at <= _end_of_day(to_date))

    if patient_uid:
        query = query.filter(
            LabTestOrder.patient_uhid.ilike(f"%{patient_uid.strip()}%")
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
        term = search.strip()
        if term:
            query = query.filter(
                or_(
                    LabTestOrder.patient_name.ilike(f"%{term}%"),
                    LabTestOrder.patient_uhid.ilike(f"%{term}%"),
                    LabTestOrder.test_name.ilike(f"%{term}%"),
                )
            )

    total = query.count()
    reports = (
        query
        .order_by(LabResult.created_at.desc(), LabResult.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    report_patient_ids = [
        report.lab_order.patient_id for report in reports if report.lab_order
    ]
    source_by_patient = _registration_sources_by_patient_id(db, report_patient_ids)
    admissions_by_patient = _active_admissions_by_patient_id(db, report_patient_ids)
    occupied_beds = _occupied_beds_by_patient_id(db)
    names = doctor_name_map(
        db,
        [report.lab_order.doctor_id for report in reports if report.lab_order],
    )

    items = [
        _serialize_list_item(
            report,
            doctor_name=names.get(report.lab_order.doctor_id) if report.lab_order else None,
            registration_source=source_by_patient.get(report.lab_order.patient_id),
            admission=admissions_by_patient.get(report.lab_order.patient_id),
            bed=occupied_beds.get(report.lab_order.patient_id),
        )
        for report in reports
        if report.lab_order
    ]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def _load_in_scope_report(
    db: Session,
    report_id: int,
    *,
    allocated_only: bool,
    nurse_id: int,
    assignment_date=None,
    shift_name: str | None = None,
) -> LabResult:
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
    if not report or not report.lab_order:
        raise HTTPException(status_code=404, detail="Report not found")

    _assert_patient_in_scope(
        db,
        report.lab_order.patient_id,
        allocated_only=allocated_only,
        nurse_id=nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    return report


def get_nurse_lab_report_service(
    db: Session,
    report_id: int,
    *,
    nurse_id: int,
    allocated_only: bool = False,
    assignment_date=None,
    shift_name: str | None = None,
):
    report = _load_in_scope_report(
        db,
        report_id,
        allocated_only=allocated_only,
        nurse_id=nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
    )
    order = report.lab_order
    occupied_beds = _occupied_beds_by_patient_id(db)
    bed = occupied_beds.get(order.patient_id)
    names = doctor_name_map(db, [order.doctor_id])
    patient_fields = _visit_location_from_bed(
        bed,
        _order_patient_fields(
            order,
            registration_source=_registration_sources_by_patient_id(
                db, [order.patient_id]
            ).get(order.patient_id),
            admission=_active_admissions_by_patient_id(db, [order.patient_id]).get(
                order.patient_id
            ),
            include_visit_location=True,
        ),
    )
    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    parameters = [
        {
            "id": parameter.id,
            "parameter_name": parameter.parameter_name,
            "value": parameter.value,
            "unit": parameter.unit,
            "normal_range": parameter.normal_range,
            "flag": parameter.flag.value if parameter.flag else None,
        }
        for parameter in (report.parameters or [])
    ]
    return {
        "id": report.id,
        "lab_test_order_id": report.lab_test_order_id,
        "uploaded_by": report.uploaded_by,
        "uploaded_by_name": _uploader_name(report.uploaded_by_user) or "",
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
            "id": order.id,
            "patient_name": order.patient_name,
            **patient_fields,
            "doctor_id": order.doctor_id,
            "doctor_name": names.get(order.doctor_id) or "",
            "department_id": order.department_id,
            "test_name": order.test_name,
            "category": order.category,
            "priority": order.priority,
            "status": status,
        },
        "parameters": parameters,
    }


def get_nurse_lab_report_file_service(
    db: Session,
    report_id: int,
    *,
    nurse_id: int,
    allocated_only: bool = False,
    assignment_date=None,
    shift_name: str | None = None,
):
    report = _load_in_scope_report(
        db,
        report_id,
        allocated_only=allocated_only,
        nurse_id=nurse_id,
        assignment_date=assignment_date,
        shift_name=shift_name,
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
