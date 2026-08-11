from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffDetailOut, StaffListItem, StaffUpdateRequest
from Services import audit_service
from Services.admin_profile_service import create_empty_admin_profile
from Services.doctor_profile_service import create_empty_doctor_profile
from Services.lab_department_helpers import validate_lab_tech_department_id
from Services.lab_technician_profile_service import create_empty_lab_technician_profile
from Services.notification_service import notify_staff_admin_update_if_inbox
from Services.nurse_profile_service import create_empty_nurse_profile
from Services.opd_billing_profile_service import create_empty_opd_billing_profile
from Services.ipd_profile_service import create_empty_ipd_profile
from Services.pharmacist_profile_service import create_empty_pharmacist_profile
from Services.receptionist_profile_service import create_empty_receptionist_profile
from Services.role_policy import assert_can_assign_role, caller_role_name
from Services.super_admin_profile_service import create_empty_super_admin_profile

IST = ZoneInfo("Asia/Kolkata")

# Role → User relationship attribute for the 1:1 module profile
_ROLE_PROFILE_ATTR = {
    "doctor": "doctor_profile",
    "nurse": "nurse_profile",
    "receptionist": "receptionist_profile",
    "lab_technician": "lab_technician_profile",
    "opd_billing": "opd_billing_profile",
    "ipd": "ipd_profile",
    "pharmacist": "pharmacist_profile",
    "admin": "admin_profile",
    "super_admin": "super_admin_profile",
}

_PROFILE_CREATE = {
    "doctor": create_empty_doctor_profile,
    "nurse": create_empty_nurse_profile,
    "receptionist": create_empty_receptionist_profile,
    "lab_technician": create_empty_lab_technician_profile,
    "opd_billing": create_empty_opd_billing_profile,
    "ipd": create_empty_ipd_profile,
    "pharmacist": create_empty_pharmacist_profile,
    "admin": create_empty_admin_profile,
    "super_admin": create_empty_super_admin_profile,
}

_ACCOUNT_PROFILE_KEYS = (
    "employee_id",
    "joining_date",
    "shift_name",
    "shift_start_time",
    "shift_end_time",
)

_SHIFT_KEYS = ("shift_name", "shift_start_time", "shift_end_time")


def _role_name(user: User) -> Optional[str]:
    return user.role_obj.name if user.role_obj else None


def _supports_shift(role_name: Optional[str]) -> bool:
    return bool(role_name) and role_name != "super_admin" and role_name in _ROLE_PROFILE_ATTR


def _get_profile(user: User, role_name: Optional[str] = None):
    name = role_name if role_name is not None else _role_name(user)
    attr = _ROLE_PROFILE_ATTR.get(name or "")
    if not attr:
        return None
    return getattr(user, attr, None)


def _ensure_profile(db: Session, user: User, role_name: str):
    profile = _get_profile(user, role_name)
    if profile is not None:
        return profile
    create_fn = _PROFILE_CREATE.get(role_name)
    if not create_fn:
        raise HTTPException(
            status_code=400,
            detail=f"No profile table for role '{role_name}'",
        )
    profile = create_fn(db, user.id)
    attr = _ROLE_PROFILE_ATTR[role_name]
    setattr(user, attr, profile)
    return profile


def _profile_account_fields(user: User) -> dict:
    role = _role_name(user)
    profile = _get_profile(user, role)
    supports = _supports_shift(role)
    if not profile:
        return {
            "employee_id": None,
            "joining_date": None,
            "shift_name": None,
            "shift_start_time": None,
            "shift_end_time": None,
            "supports_shift": supports,
        }
    return {
        "employee_id": getattr(profile, "employee_id", None),
        "joining_date": getattr(profile, "joining_date", None),
        "shift_name": getattr(profile, "shift_name", None) if supports else None,
        "shift_start_time": getattr(profile, "shift_start_time", None) if supports else None,
        "shift_end_time": getattr(profile, "shift_end_time", None) if supports else None,
        "supports_shift": supports,
    }


def _apply_account_profile_updates(
    db: Session,
    user: User,
    role_name: Optional[str],
    updates: dict,
) -> None:
    account_updates = {k: updates[k] for k in _ACCOUNT_PROFILE_KEYS if k in updates}
    if not account_updates or not role_name:
        return
    if role_name not in _ROLE_PROFILE_ATTR:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot set account profile fields for role '{role_name}'",
        )

    supports = _supports_shift(role_name)
    if not supports:
        for key in _SHIFT_KEYS:
            account_updates.pop(key, None)
        if not account_updates:
            return

    profile = _ensure_profile(db, user, role_name)

    if "employee_id" in account_updates:
        raw = account_updates["employee_id"]
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            profile.employee_id = None
        else:
            profile.employee_id = str(raw).strip()

    if "joining_date" in account_updates:
        profile.joining_date = account_updates["joining_date"]

    if supports:
        for key in _SHIFT_KEYS:
            if key not in account_updates:
                continue
            raw = account_updates[key]
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                setattr(profile, key, None)
            else:
                setattr(profile, key, str(raw).strip())


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
        **_profile_account_fields(user),
    )


def _base_query(db: Session):
    return (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.department),
            joinedload(User.doctor_profile),
            joinedload(User.nurse_profile),
            joinedload(User.receptionist_profile),
            joinedload(User.lab_technician_profile),
            joinedload(User.opd_billing_profile),
            joinedload(User.pharmacist_profile),
            joinedload(User.admin_profile),
            joinedload(User.super_admin_profile),
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
    actor: User,
) -> dict:
    if not is_active:
        _block_self_action(actor.id, user_id, "deactivate")

    user = _get_staff_or_404(db, user_id)
    user.is_active = is_active
    db.commit()

    status = "activated" if is_active else "deactivated"
    refreshed = _get_staff_or_404(db, user_id)
    notify_staff_admin_update_if_inbox(
        db,
        staff_user=refreshed,
        title="Account Updated",
        message=f"Your account was {status} by an administrator.",
        admin_user=actor,
    )
    audit_service.log_event(
        db,
        actor=actor,
        action="staff.activate" if is_active else "staff.deactivate",
        resource_type="user",
        resource_id=user.id,
        summary=f"{status.capitalize()} staff {user.email}",
        details={"email": user.email, "is_active": is_active},
    )
    return {"message": f"Staff {status} successfully", "user_id": user.id}


def update_staff(
    db: Session,
    user_id: int,
    data: StaffUpdateRequest,
    actor: User,
) -> StaffDetailOut:
    user = _get_staff_or_404(db, user_id)
    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    audit_details: dict = {"email": user.email}
    if "role_id" in updates:
        audit_details["old_role_id"] = user.role_id

    if "role_id" in updates:
        role = db.query(Role).filter(Role.id == updates["role_id"]).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        assert_can_assign_role(caller_role_name(actor), role.name)
        user.role_id = updates["role_id"]
        audit_details["new_role_id"] = updates["role_id"]
        audit_details["new_role_name"] = role.name

    # Resolve effective role after this update (new role if changed, else current)
    effective_role = (
        db.query(Role).filter(Role.id == user.role_id).first()
        if user.role_id
        else None
    )
    effective_role_name = effective_role.name if effective_role else None

    if "department_id" in updates:
        # Department is REQUIRED for doctors and lab technicians (LAB/RAD).
        # Nurses never keep users.department_id — responsibility is via bed allocation.
        if effective_role_name == "doctor":
            if updates["department_id"] is None:
                raise HTTPException(
                    status_code=400,
                    detail="department_id required for doctor",
                )
            dept = db.query(Department).filter(
                Department.id == updates["department_id"]
            ).first()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found")
            user.department_id = updates["department_id"]
        elif effective_role_name == "lab_technician":
            user.department_id = validate_lab_tech_department_id(
                db,
                updates["department_id"],
            )
        else:
            user.department_id = None
    elif effective_role_name == "lab_technician":
        # Changing role to lab_technician requires an explicit LAB/RAD department.
        if "role_id" in updates and not user.department_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "department_id required for lab_technician "
                    "(Laboratory or Radiology)"
                ),
            )
    elif effective_role_name != "doctor":
        # Role changed away from doctor/lab tech — clear department even if not in payload
        if "role_id" in updates:
            user.department_id = None
    elif effective_role_name == "doctor" and not user.department_id:
        raise HTTPException(status_code=400, detail="department_id required for doctor")

    for field in ("first_name", "last_name", "phone"):
        if field in updates:
            setattr(user, field, updates[field])

    # Ensure role_obj is current for profile resolution after role change
    if "role_id" in updates and effective_role is not None:
        user.role_obj = effective_role

    _apply_account_profile_updates(db, user, effective_role_name, updates)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Employee ID is already in use for this role",
        ) from None

    refreshed = _get_staff_or_404(db, user_id)
    if "role_id" in updates:
        new_role = refreshed.role_obj.name if refreshed.role_obj else "updated"
        notify_staff_admin_update_if_inbox(
            db,
            staff_user=refreshed,
            title="Role Updated",
            message=f"Your role was changed to {new_role} by an administrator.",
            admin_user=actor,
        )
    elif any(k in updates for k in _ACCOUNT_PROFILE_KEYS):
        notify_staff_admin_update_if_inbox(
            db,
            staff_user=refreshed,
            title="Account Updated",
            message="Your account details were updated by an administrator.",
            admin_user=actor,
        )

    audit_service.log_event(
        db,
        actor=actor,
        action="staff.update",
        resource_type="user",
        resource_id=refreshed.id,
        summary=f"Updated staff {user.email}",
        details={**audit_details, "fields": list(updates.keys())},
    )
    return _to_detail(refreshed)


def delete_staff(db: Session, user_id: int, actor: User) -> dict:
    _block_self_action(actor.id, user_id, "delete")

    user = _get_staff_or_404(db, user_id)
    user.deleted_at = datetime.now(IST)
    user.is_active = False
    db.commit()

    refreshed = _get_staff_or_404(db, user_id)
    notify_staff_admin_update_if_inbox(
        db,
        staff_user=refreshed,
        title="Account Removed",
        message="Your account was removed by an administrator.",
        admin_user=actor,
    )

    audit_service.log_event(
        db,
        actor=actor,
        action="staff.delete",
        resource_type="user",
        resource_id=user.id,
        summary=f"Deleted staff {user.email}",
        details={"email": user.email},
    )

    return {"message": "Staff deleted successfully", "user_id": user.id}
