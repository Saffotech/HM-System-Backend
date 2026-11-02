from sqlalchemy import or_
from sqlalchemy.orm import Session

from Models.department import Department
from Schemas.nurse_other_visit_schema import (
    DepartmentListResponse,
    DepartmentOption,
)


def list_departments_service(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> DepartmentListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = db.query(Department).filter(Department.is_active.is_(True))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Department.name.ilike(term),
                Department.code.ilike(term),
            )
        )

    total = query.count()
    departments = (
        query.order_by(Department.name.asc(), Department.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        DepartmentOption(
            id=department.id,
            name=department.name,
            code=department.code,
        )
        for department in departments
    ]

    return DepartmentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        departments=items,
    )
