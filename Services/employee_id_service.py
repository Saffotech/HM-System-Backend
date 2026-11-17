"""Hospital employee numbers: EMP-0001, EMP-0002, one sequence per tenant."""

import re

from fastapi import HTTPException
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session, joinedload

from Models.admin_profile import AdminProfile
from Models.doctor_profile import DoctorProfile
from Models.ipd_profile import IpdProfile
from Models.lab_technician_profile import LabTechnicianProfile
from Models.manager_profile import ManagerProfile
from Models.nurse_profile import NurseProfile
from Models.opd_billing_profile import OpdBillingProfile
from Models.pharmacist_profile import PharmacistProfile
from Models.receptionist_profile import ReceptionistProfile
from Models.role import Role  # noqa: F401 — register User.role_obj target
from Models.user import User

_ROLE_PROFILE_ATTR = {
    "doctor": "doctor_profile",
    "nurse": "nurse_profile",
    "receptionist": "receptionist_profile",
    "lab_technician": "lab_technician_profile",
    "opd_billing": "opd_billing_profile",
    "ipd": "ipd_profile",
    "pharmacist": "pharmacist_profile",
    "admin": "admin_profile",
    "manager": "manager_profile",
}

_PROFILE_MODELS = (
    DoctorProfile,
    NurseProfile,
    ReceptionistProfile,
    LabTechnicianProfile,
    OpdBillingProfile,
    IpdProfile,
    PharmacistProfile,
    AdminProfile,
    ManagerProfile,
)

_EMPLOYEE_NUMBER = re.compile(r"^EMP-(\d+)$", re.IGNORECASE)


def format_employee_id(number: int) -> str:
    return f"EMP-{number:04d}"


def allocate_employee_id(db: Session, tenant_id: int) -> str:
    number = db.execute(
        text(
            """
            INSERT INTO tenant_employee_sequences (tenant_id, last_number)
            VALUES (:tenant_id, 1)
            ON CONFLICT (tenant_id)
            DO UPDATE SET last_number = tenant_employee_sequences.last_number + 1
            RETURNING last_number
            """
        ),
        {"tenant_id": tenant_id},
    ).scalar()
    return format_employee_id(int(number))


def _employee_id_for_user(db: Session, user_id: int) -> str | None:
    for model in _PROFILE_MODELS:
        value = (
            db.query(model.employee_id)
            .filter(
                model.user_id == user_id,
                model.employee_id.isnot(None),
            )
            .scalar()
        )
        if value and str(value).strip():
            return str(value).strip()
    return None


def remember_employee_number(db: Session, tenant_id: int, employee_id: str) -> None:
    match = _EMPLOYEE_NUMBER.match(employee_id.strip())
    if not match:
        return
    number = int(match.group(1))
    db.execute(
        text(
            """
            INSERT INTO tenant_employee_sequences (tenant_id, last_number)
            VALUES (:tenant_id, :number)
            ON CONFLICT (tenant_id)
            DO UPDATE SET last_number = GREATEST(
                tenant_employee_sequences.last_number,
                EXCLUDED.last_number
            )
            """
        ),
        {"tenant_id": tenant_id, "number": number},
    )


def assert_employee_id_available(
    db: Session,
    tenant_id: int,
    employee_id: str,
    user_id: int,
) -> None:
    wanted = employee_id.strip().lower()
    for model in _PROFILE_MODELS:
        clash = (
            db.query(model.user_id)
            .join(User, User.id == model.user_id)
            .filter(
                User.tenant_id == tenant_id,
                User.id != user_id,
                func.lower(model.employee_id) == wanted,
            )
            .first()
        )
        if clash:
            raise HTTPException(
                status_code=409,
                detail="Employee ID already exists",
            )


def ensure_employee_id(db: Session, user: User, profile) -> str | None:
    """Fill a blank profile employee_id. Reuse this user's number, or take the next one."""
    if profile is None:
        return None
    current = getattr(profile, "employee_id", None)
    if current and str(current).strip():
        return str(current).strip()

    existing = _employee_id_for_user(db, user.id)
    if existing:
        profile.employee_id = existing
        return existing

    if user.tenant_id is None:
        return None

    assigned = allocate_employee_id(db, user.tenant_id)
    profile.employee_id = assigned
    return assigned


def _create_empty_profile(db: Session, role_name: str, user_id: int):
    if role_name == "doctor":
        from Services.doctor_profile_service import create_empty_doctor_profile

        return create_empty_doctor_profile(db, user_id)
    if role_name == "nurse":
        from Services.nurse_profile_service import create_empty_nurse_profile

        return create_empty_nurse_profile(db, user_id)
    if role_name == "receptionist":
        from Services.receptionist_profile_service import create_empty_receptionist_profile

        return create_empty_receptionist_profile(db, user_id)
    if role_name == "lab_technician":
        from Services.lab_technician_profile_service import create_empty_lab_technician_profile

        return create_empty_lab_technician_profile(db, user_id)
    if role_name == "opd_billing":
        from Services.opd_billing_profile_service import create_empty_opd_billing_profile

        return create_empty_opd_billing_profile(db, user_id)
    if role_name == "ipd":
        from Services.ipd_profile_service import create_empty_ipd_profile

        return create_empty_ipd_profile(db, user_id)
    if role_name == "pharmacist":
        from Services.pharmacist_profile_service import create_empty_pharmacist_profile

        return create_empty_pharmacist_profile(db, user_id)
    if role_name == "admin":
        from Services.admin_profile_service import create_empty_admin_profile

        return create_empty_admin_profile(db, user_id)
    if role_name == "manager":
        from Services.manager_profile_service import create_empty_manager_profile

        return create_empty_manager_profile(db, user_id)
    return None


def assign_missing_employee_ids(db: Session) -> int:
    """Give EMP-#### to hospital staff whose current role profile has no number."""
    bind = db.get_bind()
    if bind is None or not inspect(bind).has_table("tenant_employee_sequences"):
        return 0

    users = (
        db.query(User)
        .options(
            joinedload(User.role_obj),
            joinedload(User.doctor_profile),
            joinedload(User.nurse_profile),
            joinedload(User.receptionist_profile),
            joinedload(User.lab_technician_profile),
            joinedload(User.opd_billing_profile),
            joinedload(User.ipd_profile),
            joinedload(User.pharmacist_profile),
            joinedload(User.admin_profile),
            joinedload(User.manager_profile),
        )
        .filter(User.deleted_at.is_(None), User.tenant_id.isnot(None))
        .order_by(User.id)
        .all()
    )
    assigned = 0
    for user in users:
        role_name = user.role_obj.name if user.role_obj else None
        attr = _ROLE_PROFILE_ATTR.get(role_name or "")
        if not attr:
            continue
        profile = getattr(user, attr, None)
        if profile is not None and profile.employee_id and str(profile.employee_id).strip():
            continue
        if profile is None:
            profile = _create_empty_profile(db, role_name, user.id)
            if profile is None:
                continue
            setattr(user, attr, profile)
        ensure_employee_id(db, user, profile)
        if profile.employee_id:
            assigned += 1
    return assigned
