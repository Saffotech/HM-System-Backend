"""Patient Profile tab: personal records and hospital history.

All routes use the patient's own login token and return only that
patient's data. Billing lives in patient_billing_router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from Models.user import User
from Schemas.patient_profile_schema import PatientProfileUpdate
from Services import patient_history_service, patient_profile_service

router = APIRouter(prefix="/patient", tags=["Patient Profile"])


@router.get("/me")
def my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Header card and Personal Records."""
    return patient_profile_service.get_profile(db, current_user)


@router.patch("/me")
def update_my_profile(
    data: PatientProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit Profile. Only the fields the patient is allowed to change."""
    return patient_profile_service.update_profile(db, current_user, data)


@router.get("/me/summary")
def my_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Counts and outstanding balance for the profile landing screen."""
    return patient_profile_service.get_summary(db, current_user)


@router.get("/history/opd")
def opd_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_history_service.opd_history(db, current_user)


@router.get("/history/ipd")
def ipd_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return patient_history_service.ipd_history(db, current_user)
