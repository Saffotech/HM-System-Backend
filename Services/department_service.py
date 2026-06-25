from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.department import Department
from Schemas.department_schema import DepartmentCreate, DepartmentOut, DepartmentUpdate


def _to_out(dept: Department) -> DepartmentOut:
    return DepartmentOut(
        id=dept.id,
        name=dept.name,
        code=dept.code,
        description=dept.description,
        is_active=bool(dept.is_active),
    )


def list_departments(
    db: Session,
    is_active: Optional[bool] = None,
) -> list[DepartmentOut]:
    query = db.query(Department)
    if is_active is not None:
        query = query.filter(Department.is_active.is_(is_active))
    rows = query.order_by(Department.name).all()
    return [_to_out(d) for d in rows]


def get_department_by_id(db: Session, department_id: int) -> DepartmentOut:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return _to_out(dept)


def create_department(db: Session, data: DepartmentCreate) -> DepartmentOut:
    if data.code:
        existing = db.query(Department).filter(Department.code == data.code).first()
        if existing:
            raise HTTPException(status_code=409, detail="Department code already exists")

    existing_name = db.query(Department).filter(Department.name == data.name).first()
    if existing_name:
        raise HTTPException(status_code=409, detail="Department name already exists")

    dept = Department(
        name=data.name,
        code=data.code,
        description=data.description,
        is_active=True,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return _to_out(dept)


def update_department(
    db: Session,
    department_id: int,
    data: DepartmentUpdate,
) -> DepartmentOut:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    if data.code is not None and data.code != dept.code:
        clash = (
            db.query(Department)
            .filter(Department.code == data.code, Department.id != department_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=409, detail="Department code already exists")

    if data.name is not None and data.name != dept.name:
        clash = (
            db.query(Department)
            .filter(Department.name == data.name, Department.id != department_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=409, detail="Department name already exists")

    if data.name is not None:
        dept.name = data.name
    if data.code is not None:
        dept.code = data.code
    if data.description is not None:
        dept.description = data.description
    if data.is_active is not None:
        dept.is_active = data.is_active

    db.commit()
    db.refresh(dept)
    return _to_out(dept)
