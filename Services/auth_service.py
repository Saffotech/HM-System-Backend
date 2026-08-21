from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.role import Role
from Models.user import User
from Schemas.schemas import UserCreate
from hash import hash_password
from Services import audit_service
from Services.lab_department_helpers import validate_lab_tech_department_id
from Services.role_policy import assert_can_assign_role, caller_role_name


def register_staff(db: Session, data: UserCreate, actor: User) -> dict:
    email = (data.email or "").strip().lower()
    existing = db.query(User).filter(func.lower(User.email) == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role with id {data.role_id} not found")

    assert_can_assign_role(caller_role_name(actor), role.name)

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
    )
    db.add(new_user)
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
