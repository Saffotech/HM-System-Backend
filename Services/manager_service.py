from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.department import Department
from Models.role import Role
from Models.user import User
from Schemas.manager_schema import ManagerDashboardResponse, StaffByRoleItem
from dependencies import PLATFORM_ROLES

_STAFF_FILTER = User.deleted_at.is_(None)
_HOSPITAL_ROLE = Role.name.notin_(tuple(PLATFORM_ROLES))


def get_dashboard(db: Session, *, tenant_id: int | None) -> ManagerDashboardResponse:
    hospital_staff = _STAFF_FILTER & (User.tenant_id == tenant_id) & User.role_id.in_(
        db.query(Role.id).filter(_HOSPITAL_ROLE)
    )
    total_staff, active_staff = (
        db.query(
            func.count(User.id),
            func.count(User.id).filter(User.is_active.is_(True)),
        )
        .filter(hospital_staff)
        .one()
    )
    total_staff = int(total_staff or 0)
    active_staff = int(active_staff or 0)

    total_departments = (
        db.query(func.count(Department.id))
        .filter(Department.is_active.is_(True))
        .scalar()
    )
    total_roles = (
        db.query(func.count(Role.id))
        .filter(_HOSPITAL_ROLE)
        .scalar()
    )

    role_rows = (
        db.query(Role.id, Role.name, func.count(User.id))
        .outerjoin(User, (User.role_id == Role.id) & hospital_staff)
        .filter(_HOSPITAL_ROLE)
        .group_by(Role.id, Role.name)
        .order_by(Role.name)
        .all()
    )

    return ManagerDashboardResponse(
        total_staff=total_staff,
        active_staff=active_staff,
        inactive_staff=total_staff - active_staff,
        total_departments=int(total_departments or 0),
        total_roles=int(total_roles or 0),
        staff_by_role=[
            StaffByRoleItem(role_id=rid, role_name=name, count=int(count))
            for rid, name, count in role_rows
        ],
    )
