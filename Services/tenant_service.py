from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.hospital_settings import HospitalSettings
from Models.opd_settings import OpdSettings
from Models.role import Role
from Models.tenant import Tenant
from Models.user import User
from Schemas.tenant_schema import TenantRegisterRequest, TenantRegisterResponse
from Services import audit_service
from hash import hash_password


def _split_full_name(full_name: str) -> tuple[str, str | None]:
    parts = full_name.strip().split(None, 1)
    if not parts or not parts[0]:
        raise HTTPException(status_code=400, detail="Administrator full name is required")
    last_name = parts[1].strip() if len(parts) > 1 else None
    return parts[0], last_name or None


def register_tenant(db: Session, data: TenantRegisterRequest, actor: User) -> TenantRegisterResponse:
    code = data.code.strip().upper()
    hospital_email = str(data.email).strip().lower()
    admin_email = str(data.admin_email).strip().lower()

    if db.query(Tenant).filter(func.upper(Tenant.code) == code).first():
        raise HTTPException(status_code=409, detail="Tenant code already registered")
    if db.query(Tenant).filter(func.lower(Tenant.email) == hospital_email).first():
        raise HTTPException(status_code=409, detail="Hospital email already registered")
    if (
        db.query(User)
        .execution_options(include_all_tenants=True)
        .filter(func.lower(User.email) == admin_email)
        .first()
    ):
        raise HTTPException(status_code=409, detail="Administrator email already registered")

    role = db.query(Role).filter(Role.name == "admin").first()
    if not role:
        raise HTTPException(status_code=500, detail="Admin role is not seeded")

    first_name, last_name = _split_full_name(data.admin_full_name)

    tenant = Tenant(
        name=data.name.strip(),
        code=code,
        hospital_type=data.hospital_type.strip(),
        email=hospital_email,
        phone=data.phone.strip(),
        address=data.address.strip(),
        city=data.city.strip(),
        state=data.state.strip(),
        pincode=data.pincode.strip(),
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    db.add(
        HospitalSettings(
            tenant_id=tenant.id,
            name=tenant.name,
            address_line1=tenant.address,
            city=tenant.city,
            state=tenant.state,
            pincode=tenant.pincode,
            phone=tenant.phone,
            email=tenant.email,
        )
    )
    db.add(
        OpdSettings(
            tenant_id=tenant.id,
            allow_patient_delete=True,
            allow_appointment_delete=True,
            allow_unpaid_bill_delete=True,
            require_admin_approval_for_delete=True,
            extra={},
        )
    )

    admin = User(
        first_name=first_name,
        last_name=last_name,
        email=admin_email,
        password=hash_password(data.admin_password),
        role_id=role.id,
        phone=data.admin_phone.strip(),
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(admin)
    from seed import ensure_catalog_for_tenant

    ensure_catalog_for_tenant(db, tenant.id)
    db.commit()
    db.refresh(tenant)
    db.refresh(admin)

    audit_service.log_event(
        db,
        actor=actor,
        action="hospital.register",
        resource_type="tenant",
        resource_id=tenant.id,
        summary=f"Registered hospital {tenant.name} ({tenant.code})",
        details={
            "code": tenant.code,
            "admin_email": admin.email,
            "admin_user_id": admin.id,
        },
    )

    return TenantRegisterResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        hospital_type=tenant.hospital_type,
        admin_user_id=admin.id,
        admin_email=admin.email,
    )
