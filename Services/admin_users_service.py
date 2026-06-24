from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffDetailOut, StaffListItem, StaffUpdateRequest

IST = ZoneInfo("Asia/Kolkata")


def _to_list_item(user: User) -> StaffListItem:
    return StaffListItem(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role_id=user.role_id,
        role_name=user.role_obj.name if user.role_obj else None,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        is_active=bool(user.is_active),
        last_login=user.last_login,
        created_at=user.created_at,
    )


def _to_detail(user: User) -> StaffDetailOut:
    base = _to_list_item(user)
    return StaffDetailOut(
        **base.model_dump(),
        phone=user.phone,
        login_count=user.login_count or 0,
    )


def _base_query(db: Session):
    return (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.department),
        )
        .filter(User.deleted_at.is_(None))
    )


def _get_staff_or_404(db: Session, user_id: int) -> User:
    user = _base_query(db).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return user


def _block_self_action(actor_id: int, target_id: int, action: str) -> None:
    if actor_id == target_id:
        raise HTTPException(
            status_code=400,
            detail=f"You cannot {action} your own account",
        )


def list_staff(
    db: Session,
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    q = _base_query(db)

    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            User.first_name.ilike(term)
            | User.last_name.ilike(term)
            | User.email.ilike(term)
        )

    if role_id is not None:
        q = q.filter(User.role_id == role_id)

    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))

    total = q.count()
    rows = (
        q.order_by(User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "staff": [_to_list_item(u) for u in rows],
    }


def get_staff_by_id(db: Session, user_id: int) -> StaffDetailOut:
    return _to_detail(_get_staff_or_404(db, user_id))


def activate_staff(
    db: Session,
    user_id: int,
    is_active: bool,
    actor_id: int,
) -> dict:
    if not is_active:
        _block_self_action(actor_id, user_id, "deactivate")

    user = _get_staff_or_404(db, user_id)
    user.is_active = is_active
    db.commit()

    status = "activated" if is_active else "deactivated"
    return {"message": f"Staff {status} successfully", "user_id": user.id}


def update_staff(
    db: Session,
    user_id: int,
    data: StaffUpdateRequest,
) -> StaffDetailOut:
    user = _get_staff_or_404(db, user_id)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "role_id" in updates:
        role = db.query(Role).filter(Role.id == updates["role_id"]).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        user.role_id = updates["role_id"]

    if "department_id" in updates:
        dept = db.query(Department).filter(Department.id == updates["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        user.department_id = updates["department_id"]

    for field in ("first_name", "last_name", "phone"):
        if field in updates:
            setattr(user, field, updates[field])

    db.commit()
    db.refresh(user)
    return _to_detail(user)


def delete_staff(db: Session, user_id: int, actor_id: int) -> dict:
    _block_self_action(actor_id, user_id, "delete")

    user = _get_staff_or_404(db, user_id)
    user.deleted_at = datetime.now(IST)
    user.is_active = False
    db.commit()

    return {"message": "Staff deleted successfully", "user_id": user.id}
