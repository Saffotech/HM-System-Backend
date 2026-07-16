from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.role import Role
from Models.user import User
from Schemas.schemas import UserCreate
from hash import hash_password
from Services import audit_service
from Services.doctor_profile_service import create_empty_doctor_profile
from Services.lab_technician_profile_service import create_empty_lab_technician_profile
from Services.nurse_profile_service import create_empty_nurse_profile
from Services.receptionist_profile_service import create_empty_receptionist_profile
from Services.role_policy import assert_can_assign_role, caller_role_name


def register_staff(db: Session, data: UserCreate, actor: User) -> dict:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role with id {data.role_id} not found")

    assert_can_assign_role(caller_role_name(actor), role.name)

    if role.name in {"doctor", "nurse"} and not data.department_id:
        raise HTTPException(status_code=400, detail="department_id required for doctor/nurse")

    new_user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        password=hash_password(data.password),
        role_id=data.role_id,
        department_id=data.department_id,
        phone=data.phone,
        specialization=data.specialization,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        emergency_contact_phone=data.emergency_contact_phone,
    )
    db.add(new_user)
    db.flush()

    if role.name == "doctor":
        create_empty_doctor_profile(
            db,
            new_user.id,
            medical_license_number=data.medical_license_number,
            consultation_fee=data.consultation_fee,
        )
    elif role.name == "nurse":
        create_empty_nurse_profile(db, new_user.id)
    elif role.name == "receptionist":
        create_empty_receptionist_profile(db, new_user.id)
    elif role.name == "lab_technician":
        create_empty_lab_technician_profile(db, new_user.id)

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
