from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.registration_schema import RegisterFromLead, RegistrationOut
from Services.registration_service import get_registration, list_registrations, register_from_lead
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/registrations", tags=["Platform Registrations"])


@router.get("", response_model=list[RegistrationOut])
def read_registrations(
    status: str = Query("agreed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return list_registrations(db, current_user, status)


@router.get("/{lead_id}", response_model=RegistrationOut)
def read_registration(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return get_registration(db, current_user, lead_id)


@router.post("/{lead_id}/register", response_model=RegistrationOut, status_code=201)
def register_hospital_from_lead(
    lead_id: int,
    data: RegisterFromLead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("hospitals:create")),
):
    return register_from_lead(db, current_user, lead_id, data)
