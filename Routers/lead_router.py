from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.lead_schema import (
    LeadAgree,
    LeadClose,
    LeadContact,
    LeadCreate,
    LeadDetail,
    LeadFollowUp,
    LeadNote,
    LeadSummary,
    LeadUpdate,
)
from Services.lead_service import (
    add_note,
    agree_lead,
    claim_lead,
    close_lead,
    create_lead,
    get_lead,
    list_leads,
    log_contact,
    reopen_lead,
    schedule_follow_up,
    update_lead,
)
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/crm/leads", tags=["CRM Leads"])


@router.post("", response_model=LeadDetail, status_code=201)
def add_lead(
    data: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return create_lead(db, data, current_user)


@router.get("", response_model=list[LeadSummary])
def read_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return list_leads(db, current_user)


@router.post("/{lead_id}/claim", response_model=LeadDetail)
def claim(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return claim_lead(db, lead_id, current_user)


@router.post("/{lead_id}/contacts", response_model=LeadDetail)
def contact(
    lead_id: int,
    data: LeadContact,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return log_contact(db, lead_id, data, current_user)


@router.post("/{lead_id}/follow-up", response_model=LeadDetail)
def follow_up(
    lead_id: int,
    data: LeadFollowUp,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return schedule_follow_up(db, lead_id, data, current_user)


@router.post("/{lead_id}/notes", response_model=LeadDetail)
def note(
    lead_id: int,
    data: LeadNote,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return add_note(db, lead_id, data, current_user)


@router.post("/{lead_id}/agree", response_model=LeadDetail)
def agree(
    lead_id: int,
    data: LeadAgree,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return agree_lead(db, lead_id, data, current_user)


@router.post("/{lead_id}/close", response_model=LeadDetail)
def close(
    lead_id: int,
    data: LeadClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return close_lead(db, lead_id, data, current_user)


@router.post("/{lead_id}/reopen", response_model=LeadDetail)
def reopen(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return reopen_lead(db, lead_id, current_user)


@router.patch("/{lead_id}", response_model=LeadDetail)
def edit_lead(
    lead_id: int,
    data: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return update_lead(db, lead_id, data, current_user)


@router.get("/{lead_id}", response_model=LeadDetail)
def read_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("leads:manage")),
):
    return get_lead(db, lead_id, current_user)
