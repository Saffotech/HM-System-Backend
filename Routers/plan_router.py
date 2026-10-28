from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.plan_schema import PlanCreate, PlanUpdate
from Services.plan_service import (
    activate_plan,
    create_plan,
    deactivate_plan,
    delete_plan,
    list_plans,
    update_plan,
)
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/platform/plans", tags=["Subscription Plans"])


@router.get("")
def read_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_plans(db, current_user)


@router.post("", status_code=201)
def add_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_plan(db, current_user, data)


@router.patch("/{plan_id}")
def edit_plan(
    plan_id: int,
    data: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_plan(db, current_user, plan_id, data)


@router.post("/{plan_id}/deactivate")
def deactivate(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return deactivate_plan(db, current_user, plan_id)


@router.post("/{plan_id}/activate")
def activate(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return activate_plan(db, current_user, plan_id)


@router.delete("/{plan_id}", status_code=204)
def remove_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_plan(db, current_user, plan_id)
