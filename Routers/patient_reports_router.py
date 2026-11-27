"""Patient Reports page.

Lab Reports = hospital lab files already on lab_results for this patient.
My Uploads = files the patient adds. Prescriptions = empty for now.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from Models.user import User
from Services import patient_reports_service

router = APIRouter(prefix="/patient/reports", tags=["Patient Reports"])


@router.get("/summary")
def reports_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Counts for the three category cards on the Reports home screen."""
    return patient_reports_service.reports_summary(db, current_user)


@router.get("/lab")
def list_lab_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.list_lab_reports(db, current_user)


@router.get("/lab/{report_id}")
def get_lab_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.get_lab_report(db, current_user, report_id)


@router.get("/lab/{report_id}/file")
def download_lab_report_file(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.download_lab_report_file(
        db, current_user, report_id
    )


@router.get("/uploads")
def list_my_uploads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.list_my_uploads(db, current_user)


@router.post("/uploads", status_code=201)
async def upload_my_report(
    title: str = Form(...),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.upload_my_report(
        db,
        current_user,
        title=title,
        notes=notes,
        file=file,
    )


@router.get("/uploads/{report_id}")
def get_my_upload(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.get_my_upload(db, current_user, report_id)


@router.get("/uploads/{report_id}/file")
def download_my_upload_file(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.download_my_upload_file(
        db, current_user, report_id
    )


@router.delete("/uploads/{report_id}")
def delete_my_upload(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_reports_service.delete_my_upload(db, current_user, report_id)


@router.get("/prescriptions")
def list_prescriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Third card. Returns an empty list until that feature is built."""
    return patient_reports_service.list_prescriptions(db, current_user)
