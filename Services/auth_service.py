from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from Models.department import Department
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Schemas.schemas import PatientSelfRegister, UserCreate
from hash import hash_password
from Services import audit_service
from Services.admin_users_service import _PROFILE_CREATE
from Services.employee_id_service import ensure_employee_id
from Services.lab_department_helpers import validate_lab_tech_department_id
from Services.role_policy import assert_can_assign_role, caller_role_name


def _patient_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.name == "patient").first()
    if role is None:
        role = Role(name="patient", description="Hospital patient login")
        db.add(role)
        db.flush()
    return role


def register_patient_account(db: Session, data: PatientSelfRegister) -> dict:
    """Public signup for the patient dashboard. Does not create a visit or a bill."""
    email = str(data.email).strip().lower()
    existing = (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(User.email) == email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    hospital = (
        db.query(Tenant)
        .filter(func.lower(Tenant.code) == data.hospital_code.strip().lower(), Tenant.is_active.is_(True))
        .first()
    )
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    phone = "".join(ch for ch in data.phone if ch.isdigit())
    if len(phone) < 10:
        raise HTTPException(status_code=422, detail="Phone must be at least 10 digits")

    parts = data.full_name.strip().split(None, 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone[-15:],
        password=hash_password(data.password),
        role_id=_patient_role(db).id,
        tenant_id=hospital.id,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "Patient account created",
        "user_id": user.id,
        "email": user.email,
        "hospital_code": hospital.code,
    }


def register_staff(db: Session, data: UserCreate, actor: User) -> dict:
    email = (data.email or "").strip().lower()
    existing = (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(User.email) == email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role with id {data.role_id} not found")

    assert_can_assign_role(caller_role_name(actor), role.name)
    # Validate that the selected department exists and is active.
    if data.department_id is not None:
        department = (
            db.query(Department)
            .filter(
                Department.id == data.department_id,
                Department.is_active.is_(True),
            )
            .first()
        )

        if not department:
            raise HTTPException(
                status_code=400,
                detail="Selected department is inactive or does not exist.",
            )

    if role.name == "doctor" and not data.department_id:
        raise HTTPException(status_code=400, detail="department_id required for doctor")

    # Department required for doctors. Lab technicians should be LAB/RAD when set;
    # existing clients may omit it — lab APIs return 403 until admin assigns one.
    if role.name == "doctor":
        department_id = data.department_id
    elif role.name == "lab_technician":
        department_id = (
            validate_lab_tech_department_id(db, data.department_id)
            if data.department_id is not None
            else None
        )
    else:
        department_id = None

    new_user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=email,
        password=hash_password(data.password),
        role_id=data.role_id,
        department_id=department_id,
        tenant_id=actor.tenant_id,
    )
    db.add(new_user)
    db.flush()

    create_profile = _PROFILE_CREATE.get(role.name)
    if create_profile:
        profile = create_profile(db, new_user.id)
        ensure_employee_id(db, new_user, profile)

    db.commit()
    db.refresh(new_user)

    audit_service.log_event(
        db,
        actor=actor,
        action="staff.register",
        resource_type="user",
        resource_id=new_user.id,
        summary=f"Registered {new_user.email} as {role.name}",
        details={"email": new_user.email, "role": role.name},
    )

    return {
        "message": "Staff registered successfully",
        "user_id": new_user.id,
        "email": new_user.email,
        "role": role.name,
    }
