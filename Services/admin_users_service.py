from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Enums.notification import NotificationType, ReferenceType
from Models.department import Department
from Models.doctor_profile import DoctorProfile
from Models.nurse_profile import NurseProfile
from Models.receptionist_profile import ReceptionistProfile
from Models.role import Role
from Models.user import User
from Schemas.admin_schema import StaffDetailOut, StaffListItem, StaffUpdateRequest
from Services import audit_service
from Services.notification_service import notify_staff_admin_update
from Services.role_policy import assert_can_assign_role, caller_role_name
from Utils.shift_time import format_shift_time, parse_shift_time

IST = ZoneInfo("Asia/Kolkata")

FIELD_LABELS = {
    "consultation_fee": "Consultation fee",
    "medical_license_number": "Medical license number",
    "specialization": "Specialization",
    "department_id": "Department",
    "first_name": "First name",
    "last_name": "Last name",
    "phone": "Phone number",
    "role_id": "Role",
    "shift_name": "Shift name",
    "shift_start_time": "Shift start time",
    "shift_end_time": "Shift end time",
}

# HR/admin notifications — separate from clinical workflow alerts.
STAFF_NOTIFY_PROFILE_FIELDS = frozenset({"department_id"})
SHIFT_FIELDS = frozenset(
    {"shift_name", "shift_start_time", "shift_end_time"}
)
DEPARTMENT_NOTIFY_ROLES = frozenset({"doctor", "nurse", "receptionist"})
SHIFT_NOTIFY_ROLES = frozenset({"doctor", "nurse", "receptionist"})
ACCOUNT_NOTIFY_ROLES = frozenset({"doctor", "nurse", "receptionist"})
# Shift fields still write only to doctor / nurse / receptionist profiles.
SHIFT_ELIGIBLE_ROLES = frozenset({"doctor", "nurse", "receptionist"})


def _role_name(user: User) -> str:
    if not user.role_obj:
        raise HTTPException(status_code=500, detail="User role missing.")
    return user.role_obj.name


def _get_doctor_profile(user: User) -> Optional[DoctorProfile]:
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


def _require_nurse_profile(db: Session, user: User) -> NurseProfile:
    if _role_name(user) != "nurse":
        raise HTTPException(
            status_code=400,
            detail="Nurse profile required",
        )
    profile = user.nurse_profile
    if profile is None:
        profile = NurseProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        user.nurse_profile = profile
    return profile


def _require_receptionist_profile(
    db: Session, user: User
) -> ReceptionistProfile:
    if _role_name(user) != "receptionist":
        raise HTTPException(
            status_code=400,
            detail="Receptionist profile required",
        )
    profile = user.receptionist_profile
    if profile is None:
        profile = ReceptionistProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        user.receptionist_profile = profile
    return profile


def _apply_shift_fields(db: Session, user: User, updates: dict) -> None:
    """Write admin shift fields onto staff profile tables."""
    role = _role_name(user)
    if role == "doctor":
        profile = _require_doctor_profile(user)
    elif role == "nurse":
        profile = _require_nurse_profile(db, user)
    elif role == "receptionist":
        profile = _require_receptionist_profile(db, user)
    else:
        raise HTTPException(
            status_code=400,
            detail="Shift fields apply only to doctors, nurses, and receptionists",
        )
    for field in SHIFT_FIELDS:
        if field not in updates:
            continue
        value = updates[field]
        if field in ("shift_start_time", "shift_end_time"):
            if value is None or (isinstance(value, str) and not value.strip()):
                value = None
            else:
                try:
                    value = parse_shift_time(value)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
        setattr(profile, field, value)


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
    doctor_profile = user.doctor_profile
    nurse_profile = user.nurse_profile
    receptionist_profile = user.receptionist_profile
    role_name = user.role_obj.name if user.role_obj else None

    shift_profile = None
    if role_name == "doctor" and doctor_profile:
        shift_profile = doctor_profile
    elif role_name == "nurse" and nurse_profile:
        shift_profile = nurse_profile
    elif role_name == "receptionist" and receptionist_profile:
        shift_profile = receptionist_profile

    is_profile_completed = None
    if role_name == "doctor" and doctor_profile:
        is_profile_completed = bool(doctor_profile.is_profile_completed)
    elif role_name == "nurse" and nurse_profile:
        is_profile_completed = bool(nurse_profile.is_profile_completed)
    elif role_name == "receptionist" and receptionist_profile:
        is_profile_completed = bool(receptionist_profile.is_profile_completed)

    return StaffDetailOut(
        **base.model_dump(),
        phone=user.phone,
        login_count=user.login_count or 0,
        specialization=user.specialization,
        medical_license_number=(
            doctor_profile.medical_license_number if doctor_profile else None
        ),
        consultation_fee=(
            doctor_profile.consultation_fee if doctor_profile else None
        ),
        is_profile_completed=is_profile_completed,
        shift_name=shift_profile.shift_name if shift_profile else None,
        shift_start_time=(
            format_shift_time(shift_profile.shift_start_time)
            if shift_profile
            else None
        ),
        shift_end_time=(
            format_shift_time(shift_profile.shift_end_time)
            if shift_profile
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
            joinedload(User.nurse_profile),
            joinedload(User.receptionist_profile),
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


def _describe_staff_updates(db: Session, updates: dict) -> list[str]:
    lines: list[str] = []
    for field, value in updates.items():
        label = FIELD_LABELS.get(field, field.replace("_", " ").title())
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


def _notify_staff_if_admin_changed_profile(
    db: Session,
    user: User,
    updates: dict,
    actor: User,
) -> None:
    role = _role_name(user)
    if actor.id == user.id:
        return

    if role in DEPARTMENT_NOTIFY_ROLES:
        dept_updates = {
            key: value
            for key, value in updates.items()
            if key in STAFF_NOTIFY_PROFILE_FIELDS
        }
        if dept_updates:
            lines = _describe_staff_updates(db, dept_updates)
            if lines:
                notify_staff_admin_update(
                    db,
                    staff_user_id=user.id,
                    title="Department reassigned",
                    message=(
                        "Admin reassigned your department:\n"
                        + "\n".join(f"• {line}" for line in lines)
                    ),
                    admin_user=actor,
                    reference_type=ReferenceType.USER,
                    reference_id=user.id,
                    notification_type=NotificationType.ADMIN_UPDATE,
                )

    if role not in SHIFT_NOTIFY_ROLES:
        return

    shift_updates = {
        key: value
        for key, value in updates.items()
        if key in SHIFT_FIELDS
    }
    if not shift_updates:
        return

    lines = _describe_staff_updates(db, shift_updates)
    if not lines:
        return

    notify_staff_admin_update(
        db,
        staff_user_id=user.id,
        title="Shift updated by admin",
        message=(
            "Admin changed your duty shift:\n"
            + "\n".join(f"• {line}" for line in lines)
        ),
        admin_user=actor,
        reference_type=ReferenceType.SCHEDULE,
        reference_id=user.id,
        notification_type=NotificationType.SHIFT_UPDATED,
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

    if (
        _role_name(user) in ACCOUNT_NOTIFY_ROLES
        and actor.id != user.id
        and not is_active
    ):
        notify_staff_admin_update(
            db,
            staff_user_id=user.id,
            title="Account disabled by admin",
            message=(
                "Admin deactivated your hospital account.\n"
                "You will not be able to sign in until reactivated."
            ),
            admin_user=actor,
            reference_type=ReferenceType.USER,
            reference_id=user.id,
            notification_type=NotificationType.ADMIN_UPDATE,
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

    for field in ("first_name", "last_name", "phone", "specialization"):
        if field in updates:
            setattr(user, field, updates[field])

    doctor_admin_fields = ("medical_license_number", "consultation_fee")
    if any(field in updates for field in doctor_admin_fields):
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

    if any(field in updates for field in SHIFT_FIELDS):
        db.flush()
        user = _get_staff_or_404(db, user_id)
        _apply_shift_fields(db, user, updates)

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
    _notify_staff_if_admin_changed_profile(db, user, updates, actor)

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

    if _role_name(user) in ACCOUNT_NOTIFY_ROLES and actor.id != user.id:
        notify_staff_admin_update(
            db,
            staff_user_id=user.id,
            title="Account removed by admin",
            message="Admin deactivated and removed your hospital account.",
            admin_user=actor,
            reference_type=ReferenceType.USER,
            reference_id=user.id,
            notification_type=NotificationType.ADMIN_UPDATE,
        )

    return {"message": "Staff deleted successfully", "user_id": user.id}
