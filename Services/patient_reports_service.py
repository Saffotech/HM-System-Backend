"""Patient Reports page.

Three cards on the template:

1. Lab Reports — hospital lab PDFs already stored on lab_results for this patient.
2. My Uploads — files the patient adds themselves (patient_uploaded_reports).
3. Prescriptions — left empty for a later release.

A patient only sees their own rows. Lab listing reuses the same LabResult
files the doctor and nurse already open.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from Models.doctor_lab_test_order import LabTestOrder
from Models.lab_result import LabResult
from Models.patient_uploaded_report import PatientUploadedReport
from Models.user import User
from Services.patient_portal_service import patient_for_user

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
EXTENSION_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_FILE_SIZE = 10 * 1024 * 1024


def _upload_dir() -> Path:
    path = Path(os.getenv("PATIENT_UPLOAD_DIR", "uploads/patient_reports"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_relative(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def _resolve_path(stored_path: str, *, base_dir: Path) -> Path:
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    base = base_dir.resolve()
    if base not in candidate.parents and candidate != base:
        # Allow files that live under the shared uploads root.
        uploads_root = Path("uploads").resolve()
        if uploads_root not in candidate.parents and candidate != uploads_root:
            raise HTTPException(status_code=404, detail="File not found")
    return candidate


def reports_summary(db: Session, user: User) -> dict:
    """Counts for the three category cards. Prescriptions stay at 0 for now."""
    patient = patient_for_user(db, user)
    lab_count = (
        db.query(LabResult.id)
        .join(LabTestOrder, LabTestOrder.id == LabResult.lab_test_order_id)
        .filter(LabTestOrder.patient_id == patient.id)
        .count()
    )
    upload_count = (
        db.query(PatientUploadedReport.id)
        .filter(PatientUploadedReport.patient_id == patient.id)
        .count()
    )
    return {
        "lab_reports": lab_count,
        "my_uploads": upload_count,
        "prescriptions": 0,
    }


def list_lab_reports(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    rows = (
        db.query(LabResult)
        .options(joinedload(LabResult.lab_order))
        .join(LabTestOrder, LabTestOrder.id == LabResult.lab_test_order_id)
        .filter(LabTestOrder.patient_id == patient.id)
        .order_by(LabResult.created_at.desc(), LabResult.id.desc())
        .all()
    )
    reports = []
    for report in rows:
        order = report.lab_order
        reports.append(
            {
                "report_id": report.id,
                "order_id": order.id if order else None,
                "test_name": order.test_name if order else None,
                "category": order.category if order else None,
                "file_name": report.file_name,
                "file_type": report.file_type,
                "has_file": bool(report.report_file),
                "uploaded_at": report.created_at,
            }
        )
    return {"total": len(reports), "reports": reports}


def get_lab_report(db: Session, user: User, report_id: int) -> dict:
    """Same shape a doctor sees for one report, scoped to this patient."""
    patient = patient_for_user(db, user)
    report = (
        db.query(LabResult)
        .options(
            joinedload(LabResult.parameters),
            joinedload(LabResult.uploaded_by_user),
            joinedload(LabResult.lab_order),
        )
        .join(LabTestOrder, LabTestOrder.id == LabResult.lab_test_order_id)
        .filter(
            LabResult.id == report_id,
            LabTestOrder.patient_id == patient.id,
        )
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Lab report not found")

    order = report.lab_order
    uploader = report.uploaded_by_user
    uploader_name = " ".join(
        filter(None, [uploader.first_name if uploader else None, uploader.last_name if uploader else None])
    )
    return {
        "report_id": report.id,
        "order_id": order.id if order else None,
        "test_name": order.test_name if order else None,
        "category": order.category if order else None,
        "priority": order.priority if order else None,
        "order_status": order.status.value if order and order.status else None,
        "sample_collected_at": report.sample_collected_at,
        "test_performed_at": report.test_performed_at,
        "remarks": report.remarks,
        "file_name": report.file_name,
        "file_type": report.file_type,
        "file_size": report.file_size,
        "has_file": bool(report.report_file),
        "uploaded_by_name": uploader_name or None,
        "uploaded_at": report.created_at,
        "parameters": [
            {
                "id": parameter.id,
                "parameter_name": parameter.parameter_name,
                "value": parameter.value,
                "unit": parameter.unit,
                "normal_range": parameter.normal_range,
                "flag": parameter.flag.value if parameter.flag else None,
            }
            for parameter in (report.parameters or [])
        ],
    }


def download_lab_report_file(db: Session, user: User, report_id: int) -> FileResponse:
    from Services.lab_service import _resolve_report_path

    patient = patient_for_user(db, user)
    report = (
        db.query(LabResult)
        .join(LabTestOrder, LabTestOrder.id == LabResult.lab_test_order_id)
        .filter(
            LabResult.id == report_id,
            LabTestOrder.patient_id == patient.id,
        )
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Lab report not found")
    if not report.report_file:
        raise HTTPException(status_code=404, detail="No file uploaded")

    file_path = _resolve_report_path(report.report_file)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = report.file_type or EXTENSION_MEDIA_TYPES.get(
        file_path.suffix.lower(), "application/octet-stream"
    )
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=report.file_name or file_path.name,
    )


def _upload_out(row: PatientUploadedReport) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "notes": row.notes,
        "file_name": row.file_name,
        "file_type": row.file_type,
        "file_size": row.file_size,
        "uploaded_at": row.created_at,
    }


def list_my_uploads(db: Session, user: User) -> dict:
    patient = patient_for_user(db, user)
    rows = (
        db.query(PatientUploadedReport)
        .filter(PatientUploadedReport.patient_id == patient.id)
        .order_by(PatientUploadedReport.created_at.desc(), PatientUploadedReport.id.desc())
        .all()
    )
    return {"total": len(rows), "reports": [_upload_out(row) for row in rows]}


def get_my_upload(db: Session, user: User, report_id: int) -> dict:
    patient = patient_for_user(db, user)
    row = (
        db.query(PatientUploadedReport)
        .filter(
            PatientUploadedReport.id == report_id,
            PatientUploadedReport.patient_id == patient.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return _upload_out(row)


def upload_my_report(
    db: Session,
    user: User,
    *,
    title: str,
    notes: str | None,
    file: UploadFile,
) -> dict:
    patient = patient_for_user(db, user)
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="Title is required")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG and PNG files are allowed",
        )

    file.file.seek(0)
    file_size = file.size if file.size is not None else len(file.file.read())
    file.file.seek(0)
    if file_size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10 MB")

    unique_name = f"{uuid.uuid4()}{extension}"
    absolute_path = _upload_dir() / unique_name
    stored_path = _store_relative(unique_name)

    try:
        with open(absolute_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        logger.exception("Failed to save patient upload for patient %s", patient.id)
        raise HTTPException(status_code=500, detail="Failed to save file") from exc

    row = PatientUploadedReport(
        patient_id=patient.id,
        uploaded_by_user_id=user.id,
        title=clean_title[:200],
        notes=(notes or "").strip() or None,
        report_file=stored_path,
        file_name=file.filename,
        file_type=file.content_type or EXTENSION_MEDIA_TYPES.get(extension),
        file_size=file_size,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        if absolute_path.exists():
            try:
                absolute_path.unlink()
            except OSError:
                logger.warning("Could not remove orphaned patient file %s", absolute_path)
        raise

    return {
        "message": "Report uploaded",
        **_upload_out(row),
    }


def download_my_upload_file(db: Session, user: User, report_id: int) -> FileResponse:
    patient = patient_for_user(db, user)
    row = (
        db.query(PatientUploadedReport)
        .filter(
            PatientUploadedReport.id == report_id,
            PatientUploadedReport.patient_id == patient.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_path = _resolve_path(row.report_file, base_dir=_upload_dir())
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = row.file_type or EXTENSION_MEDIA_TYPES.get(
        file_path.suffix.lower(), "application/octet-stream"
    )
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=row.file_name or file_path.name,
    )


def delete_my_upload(db: Session, user: User, report_id: int) -> dict:
    patient = patient_for_user(db, user)
    row = (
        db.query(PatientUploadedReport)
        .filter(
            PatientUploadedReport.id == report_id,
            PatientUploadedReport.patient_id == patient.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    stored = row.report_file
    db.delete(row)
    db.commit()

    if stored:
        try:
            path = _resolve_path(stored, base_dir=_upload_dir())
            if path.exists():
                path.unlink()
        except Exception:
            logger.warning("Could not remove patient upload file %s", stored)

    return {"message": "Upload deleted", "id": report_id}


def list_prescriptions(db: Session, user: User) -> dict:
    """Placeholder for the third card. Not implemented yet."""
    patient_for_user(db, user)
    return {
        "total": 0,
        "prescriptions": [],
        "message": "Prescriptions will be available in a later release",
    }
