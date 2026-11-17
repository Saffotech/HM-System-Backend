
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.department import Department
from Models.user import User
from Schemas.department_schema import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
)
from Services import audit_service


def _to_out(dept: Department) -> DepartmentOut:
    return DepartmentOut(
        id=dept.id,
        name=dept.name,
        code=dept.code,
        description=dept.description,
        kind=dept.kind if dept.kind in ("doctor", "lab") else "doctor",
        is_active=bool(dept.is_active),
    )


def _normalize_department_name(name: str) -> str:
    name = name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Department name cannot be empty",
        )

    # Name must contain at least one alphabetic character.
    # Only letters, numbers, and spaces are allowed.
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]*", name):
        raise HTTPException(
            status_code=422,
            detail="Department name must start with a letter and contain only letters, numbers, and spaces",
        )

    return name


def _normalize_department_code(code: Optional[str]) -> Optional[str]:
    if code is None or not code.strip():
        return None

    code = code.strip()

    # Code must contain at least one alphabetic character.
    # Only letters and numbers are allowed.
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", code):
        raise HTTPException(
            status_code=422,
            detail="Department code must start with a letter and contain only letters and numbers",
        )

    return code


def list_departments(
    db: Session,
    is_active: Optional[bool] = None,
) -> list[DepartmentOut]:

    query = db.query(Department)

    if is_active is not None:
        query = query.filter(
            Department.is_active.is_(is_active)
        )

    rows = query.order_by(Department.name).all()

    return [_to_out(dept) for dept in rows]


def get_department_by_id(
    db: Session,
    department_id: int,
) -> DepartmentOut:

    dept = (
        db.query(Department)
        .filter(Department.id == department_id)
        .first()
    )

    if not dept:
        raise HTTPException(
            status_code=404,
            detail="Department not found",
        )

    return _to_out(dept)


def create_department(
    db: Session,
    data: DepartmentCreate,
    actor: User,
) -> DepartmentOut:

    # Validate and normalize department name
    department_name = _normalize_department_name(data.name)

    # Validate and normalize optional department code
    department_code = _normalize_department_code(data.code)

    # Check duplicate department name (case-insensitive)
    existing_name = (
        db.query(Department)
        .filter(
            func.lower(func.trim(Department.name))
            == department_name.lower()
        )
        .first()
    )

    if existing_name:
        raise HTTPException(
            status_code=409,
            detail="Department name already exists",
        )

    # Check duplicate department code (case-insensitive)
    if department_code:
        existing_code = (
            db.query(Department)
            .filter(
                func.lower(func.trim(Department.code))
                == department_code.lower()
            )
            .first()
        )

        if existing_code:
            raise HTTPException(
                status_code=409,
                detail="Department code already exists",
            )

    dept = Department(
        name=department_name,
        code=department_code,
        description=data.description,
        kind=data.kind,
        is_active=True,
    )

    try:
        db.add(dept)
        db.commit()
        db.refresh(dept)

    except Exception:
        db.rollback()
        raise

    audit_service.log_event(
        db,
        actor=actor,
        action="department.create",
        resource_type="department",
        resource_id=dept.id,
        summary=f"Created department {dept.name}",
        details={
            "name": dept.name,
            "code": dept.code,
            "kind": dept.kind,
        },
    )

    return _to_out(dept)


def update_department(
    db: Session,
    department_id: int,
    data: DepartmentUpdate,
    actor: User,
) -> DepartmentOut:

    dept = (
        db.query(Department)
        .filter(Department.id == department_id)
        .first()
    )

    if not dept:
        raise HTTPException(
            status_code=404,
            detail="Department not found",
        )

    # Validate department name
    if data.name is not None:

        department_name = _normalize_department_name(data.name)

        clash = (
            db.query(Department)
            .filter(
                func.lower(func.trim(Department.name))
                == department_name.lower(),
                Department.id != department_id,
            )
            .first()
        )

        if clash:
            raise HTTPException(
                status_code=409,
                detail="Department name already exists",
            )

        dept.name = department_name

    # Validate department code
    if data.code is not None:

        department_code = _normalize_department_code(data.code)

        if department_code:
            clash = (
                db.query(Department)
                .filter(
                    func.lower(func.trim(Department.code))
                    == department_code.lower(),
                    Department.id != department_id,
                )
                .first()
            )

            if clash:
                raise HTTPException(
                    status_code=409,
                    detail="Department code already exists",
                )

        dept.code = department_code

    # Update remaining fields
    if data.description is not None:
        dept.description = data.description

    if data.kind is not None:
        dept.kind = data.kind

    if data.is_active is not None:
        dept.is_active = data.is_active

    try:
        db.commit()
        db.refresh(dept)

    except Exception:
        db.rollback()
        raise

    audit_service.log_event(
        db,
        actor=actor,
        action="department.update",
        resource_type="department",
        resource_id=dept.id,
        summary=f"Updated department {dept.name}",
        details=data.model_dump(exclude_unset=True),
    )

    return _to_out(dept)
