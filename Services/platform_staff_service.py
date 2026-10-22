from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.role import Role
from Models.user import User
from Schemas.platform_staff_schema import PlatformStaffCreate, PlatformStaffOut
from Services import audit_service
from Services.role_policy import caller_role_name
from hash import hash_password

PLATFORM_STAFF_ROLES = frozenset({"crm", "accountant"})


def create_platform_staff(db: Session, data: PlatformStaffCreate, actor: User) -> PlatformStaffOut:
    if caller_role_name(actor) != "platform_admin":
        raise HTTPException(status_code=403, detail="Only a platform admin can create platform staff")

    role_name = data.role
    if role_name not in PLATFORM_STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Role must be crm or accountant")

    email = str(data.email).strip().lower()
    existing = (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(User.email) == email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    role = (
        db.query(Role)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(Role.name) == role_name)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' is not configured")

    new_user = User(
        first_name=data.first_name.strip(),
        last_name=(data.last_name or "").strip() or None,
        email=email,
        password=hash_password(data.password),
        role_id=role.id,
        tenant_id=None,
        department_id=None,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    audit_service.log_event(
        db,
        actor=actor,
        action="platform_staff.create",
        resource_type="user",
        resource_id=new_user.id,
        summary=f"Created {role.name} staff {new_user.email}",
        details={"email": new_user.email, "role": role.name},
    )

    return PlatformStaffOut(
        message="Staff created successfully",
        user_id=new_user.id,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        email=new_user.email,
        role=role.name,
        tenant_id=None,
        is_active=bool(new_user.is_active),
    )
