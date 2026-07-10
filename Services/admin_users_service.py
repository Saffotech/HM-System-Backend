from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.doctor_profile import DoctorProfile
from Models.role import Role
from Models.user import User
from Enums.notification import ReferenceType
from Schemas.admin_schema import StaffDetailOut, StaffListItem, StaffUpdateRequest
from Services import audit_service
from Services.notification_service import notify_doctor_admin_update
from Services.role_policy import assert_can_assign_role, caller_role_name

IST = ZoneInfo("Asia/Kolkata")

DOCTOR_FIELD_LABELS = {
    "consultation_fee": "Consultation fee",
    "medical_license_number": "Medical license number",
    "specialization": "Specialization",
    "department_id": "Department",
    "first_name": "First name",
    "last_name": "Last name",
    "phone": "Phone number",
    "role_id": "Role",
}

# Only department reassignment warrants a doctor inbox notification.
DOCTOR_NOTIFY_PROFILE_FIELDS = frozenset({"department_id"})


def _role_name(user: User) -> str:
    if not user.role_obj:
        raise HTTPException(status_code=500, detail="User role missing.")
    return user.role_obj.name


def _get_doctor_profile(user: User) -> Optional[DoctorProfile]:
    """Return doctor_profiles row for doctors; None for other roles."""
    if _role_name(user) != "doctor":
        return None
    return user.doctor_profile


def _require_doctor_profile(user: User) -> DoctorProfile:
    profile = _get_doctor_profile(user)
    if profile is None:
        raise HTTPException(
            status_code=500,
            detail="Doctor profile not found.",
        )
    return profile


def _assert_unique_medical_license(
    db: Session,
    license_number: Optional[str],
    user_id: int,
) -> None:
    if not license_number:
        return
    existing = (
        db.query(DoctorProfile)
        .filter(
            DoctorProfile.medical_license_number == license_number,
            DoctorProfile.user_id != user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Medical license number already exists.",
        )


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
    profile = user.doctor_profile
    role_name = user.role_obj.name if user.role_obj else None
    return StaffDetailOut(
        **base.model_dump(),
        phone=user.phone,
        login_count=user.login_count or 0,
        specialization=user.specialization,
        medical_license_number=profile.medical_license_number if profile else None,
        consultation_fee=profile.consultation_fee if profile else None,
        is_profile_completed=(
            bool(profile.is_profile_completed)
            if profile and role_name == "doctor"
            else None
        ),
    )


def _base_query(db: Session):
    return (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.department),
            joinedload(User.doctor_profile),
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


def _describe_staff_updates(db: Session, user: User, updates: dict) -> list[str]:
    lines: list[str] = []
    for field, value in updates.items():
        label = DOCTOR_FIELD_LABELS.get(field, field.replace("_", " ").title())
        if field == "department_id" and value is not None:
            dept = db.query(Department).filter(Department.id == value).first()
            display = dept.name if dept else str(value)
            lines.append(f"{label}: {display}")
        elif field == "role_id" and value is not None:
            role = db.query(Role).filter(Role.id == value).first()
            display = role.name if role else str(value)
            lines.append(f"{label}: {display}")
        elif field == "consultation_fee" and value is not None:
            lines.append(f"{label}: {value}")
        else:
            lines.append(f"{label}: {value}")
    return lines


def _notify_doctor_if_admin_changed_profile(
    db: Session,
    user: User,
    updates: dict,
    actor: User,
    *,
    title: str,
    message_prefix: str,
) -> None:
    if _role_name(user) != "doctor":
        return
    if actor.id == user.id:
        return

    relevant_updates = {
        key: value
        for key, value in updates.items()
        if key in DOCTOR_NOTIFY_PROFILE_FIELDS
    }
    if not relevant_updates:
        return

    lines = _describe_staff_updates(db, user, relevant_updates)
    if not lines:
        return

    notify_doctor_admin_update(
        db,
        doctor_user_id=user.id,
        title=title,
        message=f"{message_prefix}\n" + "\n".join(f"• {line}" for line in lines),
        admin_user=actor,
        reference_type=ReferenceType.USER,
        reference_id=user.id,
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
    audit_service.log_event(
        db,
        actor=actor,
        action="staff.activate" if is_active else "staff.deactivate",
        resource_type="user",
        resource_id=user.id,
        summary=f"{status.capitalize()} staff {user.email}",
        details={"email": user.email, "is_active": is_active},
    )

    if _role_name(user) == "doctor" and actor.id != user.id and not is_active:
        notify_doctor_admin_update(
            db,
            doctor_user_id=user.id,
            title="Account disabled by admin",
            message=(
                "Admin deactivated your hospital account.\n"
                "You will not be able to sign in until reactivated."
            ),
            admin_user=actor,
            reference_type=ReferenceType.USER,
            reference_id=user.id,
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

    if "department_id" in updates:
        dept = db.query(Department).filter(Department.id == updates["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        user.department_id = updates["department_id"]

    # Admin may correct employment identity (names) and contact details.
    for field in ("first_name", "last_name", "phone", "specialization"):
        if field in updates:
            setattr(user, field, updates[field])

    doctor_admin_fields = ("medical_license_number", "consultation_fee")
    if any(field in updates for field in doctor_admin_fields):
        # Role may have just changed in this request — reload relationships.
        db.flush()
        user = _get_staff_or_404(db, user_id)

        if _role_name(user) != "doctor":
            raise HTTPException(
                status_code=400,
                detail="medical_license_number and consultation_fee apply only to doctors",
            )

        profile = _require_doctor_profile(user)

        if "medical_license_number" in updates:
            _assert_unique_medical_license(
                db,
                updates["medical_license_number"],
                user.id,
            )
            profile.medical_license_number = updates["medical_license_number"]
        if "consultation_fee" in updates:
            profile.consultation_fee = updates["consultation_fee"]

    db.commit()

    audit_service.log_event(
        db,
        actor=actor,
        action="staff.update",
        resource_type="user",
        resource_id=user.id,
        summary=f"Updated staff {user.email}",
        details={**audit_details, "fields": list(updates.keys())},
    )

    user = _get_staff_or_404(db, user_id)
    _notify_doctor_if_admin_changed_profile(
        db,
        user,
        updates,
        actor,
        title="Department reassigned",
        message_prefix="Admin reassigned your department:",
    )

    return _to_detail(user)


def delete_staff(db: Session, user_id: int, actor: User) -> dict:
    _block_self_action(actor.id, user_id, "delete")

    user = _get_staff_or_404(db, user_id)
    user.deleted_at = datetime.now(IST)
    user.is_active = False
    db.commit()

    audit_service.log_event(
        db,
        actor=actor,
        action="staff.delete",
        resource_type="user",
        resource_id=user.id,
        summary=f"Deleted staff {user.email}",
        details={"email": user.email},
    )

    if _role_name(user) == "doctor" and actor.id != user.id:
        notify_doctor_admin_update(
            db,
            doctor_user_id=user.id,
            title="Account removed by admin",
            message="Admin deactivated and removed your hospital account.",
            admin_user=actor,
            reference_type=ReferenceType.USER,
            reference_id=user.id,
        )

    return {"message": "Staff deleted successfully", "user_id": user.id}
