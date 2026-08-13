"""Laboratory vs Radiology department helpers for lab orders and lab techs."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session, Query

from Models.department import Department
from Models.doctor_lab_test_order import LabTestOrder
from Models.user import User

LAB_DEPARTMENT_CODE = "LAB"
RADIOLOGY_DEPARTMENT_CODE = "RAD"
LAB_DEPARTMENT_CODES = frozenset({LAB_DEPARTMENT_CODE, RADIOLOGY_DEPARTMENT_CODE})

_RADIOLOGY_CATEGORY_TOKENS = frozenset(
    {
        "radiology",
        "imaging",
        "x-ray",
        "xray",
        "mri",
        "ct",
        "usg",
        "ultrasound",
        "mammography",
        "mammogram",
    }
)

_RADIOLOGY_TEST_TOKENS = (
    "x-ray",
    "xray",
    "mri",
    "ct scan",
    "ct-",
    "ultrasound",
    "usg",
    "mammograph",
    "mammogram",
)


def get_lab_department_by_code(db: Session, code: str) -> Department:
    dept = (
        db.query(Department)
        .filter(Department.code == code, Department.is_active.is_(True))
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Lab department '{code}' is not configured. "
                "Run seed to create Laboratory (LAB) and Radiology (RAD)."
            ),
        )
    return dept


def get_lab_department_or_404(db: Session, department_id: int) -> Department:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    if (dept.code or "").upper() not in LAB_DEPARTMENT_CODES:
        raise HTTPException(
            status_code=400,
            detail="department_id must be Laboratory (LAB) or Radiology (RAD)",
        )
    return dept


def _looks_like_radiology(*, category: str | None, test_name: str | None) -> bool:
    category_key = (category or "").strip().casefold()
    if category_key in _RADIOLOGY_CATEGORY_TOKENS:
        return True
    if any(token in category_key for token in _RADIOLOGY_CATEGORY_TOKENS):
        return True

    test_key = (test_name or "").strip().casefold()
    return any(token in test_key for token in _RADIOLOGY_TEST_TOKENS)


def resolve_lab_department_id(
    db: Session,
    *,
    department_id: int | None = None,
    category: str | None = None,
    test_name: str | None = None,
) -> int:
    """Resolve Laboratory/Radiology department for an order.

    Prefer explicit department_id. Otherwise infer from category/test_name so
    existing clients that only send category keep working.
    """
    if department_id is not None:
        return get_lab_department_or_404(db, department_id).id

    code = (
        RADIOLOGY_DEPARTMENT_CODE
        if _looks_like_radiology(category=category, test_name=test_name)
        else LAB_DEPARTMENT_CODE
    )
    return get_lab_department_by_code(db, code).id


def require_lab_tech_department_id(user: User) -> int:
    if not user.department_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Lab technician has no department assigned. "
                "Admin must set Laboratory (LAB) or Radiology (RAD)."
            ),
        )
    return user.department_id


def assert_order_accessible_by_lab_tech(order: LabTestOrder, user: User) -> None:
    tech_dept_id = require_lab_tech_department_id(user)
    if order.department_id is None or order.department_id != tech_dept_id:
        raise HTTPException(status_code=404, detail="Lab order not found")


def filter_orders_for_lab_tech(query: Query, user: User) -> Query:
    tech_dept_id = require_lab_tech_department_id(user)
    return query.filter(LabTestOrder.department_id == tech_dept_id)


def validate_lab_tech_department_id(db: Session, department_id: int | None) -> int:
    if department_id is None:
        raise HTTPException(
            status_code=400,
            detail="department_id required for lab_technician (Laboratory or Radiology)",
        )
    return get_lab_department_or_404(db, department_id).id
