from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from Models.department import Department
from Models.lab_test import LabTest
from Models.user import User
from Schemas.lab_test_schema import (
    LabTestActivation,
    LabTestCreate,
    LabTestResponse,
    LabTestUpdate,
)
from Services import audit_service

_ALLOWED_DEPARTMENT_CODES = frozenset({"LAB", "RAD"})


def _normalize_name(name: str) -> str:
    return " ".join(name.split())


def _get_department(db: Session, department_id: int) -> Department:
    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.is_active.is_(True),
        )
        .first()
    )
    if not department or (department.code or "").upper() not in _ALLOWED_DEPARTMENT_CODES:
        raise HTTPException(
            status_code=400,
            detail="Lab catalog tests must belong to an active Laboratory or Radiology department",
        )
    return department


def _get_test(db: Session, test_id: int) -> LabTest:
    test = db.query(LabTest).filter(LabTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Lab catalog test not found")
    return test


def _ensure_unique(
    db: Session,
    *,
    test_name: str,
    department_id: int | None,
    test_id: int | None = None,
) -> None:
    query = db.query(LabTest).filter(
        LabTest.test_name.ilike(test_name),
        LabTest.department_id == department_id,
    )
    if test_id is not None:
        query = query.filter(LabTest.id != test_id)
    if query.first():
        raise HTTPException(
            status_code=409,
            detail="A lab test with this name already exists in the selected department",
        )


def _to_response(test: LabTest) -> LabTestResponse:
    return LabTestResponse.model_validate(test)

def resolve_catalog_test(
    db: Session,
    *,
    lab_test_id: int | None,
    test_name: str | None,
    department_id: int,
) -> LabTest:
    """Resolve an active catalog test and provide its server-owned values.

    The name fallback keeps existing clients working during the frontend
    migration. It is exact within the resolved department and never accepts a
    client-provided price.
    """
    if lab_test_id is not None:
        test = (
            db.query(LabTest)
            .options(joinedload(LabTest.department))
            .filter(LabTest.id == lab_test_id)
            .first()
        )
        if not test:
            raise HTTPException(status_code=404, detail="Lab catalog test not found")
        if not test.active:
            raise HTTPException(status_code=400, detail="Lab catalog test is inactive")
        if department_id is not None and test.department_id != department_id:
            raise HTTPException(
                status_code=400,
                detail="Lab catalog test does not belong to the selected department",
            )
        return test

    normalized_name = _normalize_name(test_name or "")
    if not normalized_name:
        raise HTTPException(status_code=400, detail="A lab catalog test is required")
    test = (
        db.query(LabTest)
        .options(joinedload(LabTest.department))
        .filter(
            LabTest.test_name.ilike(normalized_name),
            LabTest.department_id == department_id,
        )
        .first()
    )
    if not test:
        raise HTTPException(
            status_code=400,
            detail="The selected lab test is not available in the catalog",
        )
    if not test.active:
        raise HTTPException(status_code=400, detail="Lab catalog test is inactive")
    return test

def list_lab_tests(
    db: Session,
    *,
    active: bool | None = None,
    department_id: int | None = None,
) -> list[LabTestResponse]:
    query = db.query(LabTest)
    if active is not None:
        query = query.filter(LabTest.active.is_(active))
    if department_id is not None:
        query = query.filter(LabTest.department_id == department_id)
    return [_to_response(test) for test in query.order_by(LabTest.test_name).all()]


def create_lab_test(
    db: Session,
    data: LabTestCreate,
    actor: User,
) -> LabTestResponse:
    name = _normalize_name(data.test_name)
    department = _get_department(db, data.department_id)
    _ensure_unique(db, test_name=name, department_id=department.id)

    test = LabTest(
        test_name=name,
        department_id=department.id,
        price=data.price,
        active=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    audit_service.log_event(
        db,
        actor=actor,
        action="lab_catalog.create",
        resource_type="lab_test",
        resource_id=test.id,
        summary=f"Created lab catalog test {test.test_name}",
        details={
            "test_name": test.test_name,
            "department_id": test.department_id,
            "price": str(test.price),
        },
    )
    return _to_response(test)


def update_lab_test(
    db: Session,
    test_id: int,
    data: LabTestUpdate,
    actor: User,
) -> LabTestResponse:
    test = _get_test(db, test_id)
    updates = data.model_dump(exclude_unset=True)
    department_id = updates.get("department_id", test.department_id)
    name = _normalize_name(updates["test_name"]) if "test_name" in updates else test.test_name

    _get_department(db, department_id)
    _ensure_unique(
        db,
        test_name=name,
        department_id=department_id,
        test_id=test.id,
    )

    test.test_name = name
    test.department_id = department_id
    if "price" in updates:
        test.price = updates["price"]

    db.commit()
    db.refresh(test)
    audit_service.log_event(
        db,
        actor=actor,
        action="lab_catalog.update",
        resource_type="lab_test",
        resource_id=test.id,
        summary=f"Updated lab catalog test {test.test_name}",
        details={key: str(value) for key, value in updates.items()},
    )
    return _to_response(test)


def set_lab_test_active(
    db: Session,
    test_id: int,
    data: LabTestActivation,
    actor: User,
) -> LabTestResponse:
    test = _get_test(db, test_id)
    test.active = data.active
    db.commit()
    db.refresh(test)
    audit_service.log_event(
        db,
        actor=actor,
        action="lab_catalog.activate" if data.active else "lab_catalog.deactivate",
        resource_type="lab_test",
        resource_id=test.id,
        summary=f"{'Activated' if data.active else 'Deactivated'} lab catalog test {test.test_name}",
        details={"active": data.active},
    )
    return _to_response(test)
