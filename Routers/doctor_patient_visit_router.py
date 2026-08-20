from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_doctor_visit_schema import DoctorPatientVisitsResponse
from Services.nurse_doctor_visit_service import get_doctor_patient_visits_service

router = APIRouter(
    prefix="/doctor/patient-visits",
    tags=["Doctor Patient Visits"],
)


@router.get(
    "",
    response_model=DoctorPatientVisitsResponse,
    status_code=status.HTTP_200_OK,
)
def get_doctor_patient_visits(
    patient_id: int | None = Query(None, ge=1),
    patient_uid: str | None = Query(None),
    visit_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_patient_visits:view")),
):
    return get_doctor_patient_visits_service(
        db,
        doctor_id=current_user.id,
        patient_id=patient_id,
        patient_uid=patient_uid,
        visit_date=visit_date,
    )
