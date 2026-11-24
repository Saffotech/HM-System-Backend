"""Hospital-specific copies of global role templates.

Global ``role_permissions`` remain the template used for a new hospital.
Once ``tenant_role_permission_state`` exists for a tenant and role, that
hospital's grants are the only source of truth, including an empty set.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from Models.role import RolePermission, TenantRolePermission, TenantRolePermissionState
from Models.user import User


def has_tenant_set(db: Session, tenant_id: int, role_id: int) -> bool:
    return (
        db.query(TenantRolePermissionState)
        .filter(
            TenantRolePermissionState.tenant_id == tenant_id,
            TenantRolePermissionState.role_id == role_id,
        )
        .first()
        is not None
    )


def permission_names_for_user(db: Session, user: User) -> list[str]:
    if not user.role_obj:
        return []
    if user.tenant_id is None or user.role_id is None:
        return [p.name for p in (user.role_obj.permissions or [])]
    if not has_tenant_set(db, user.tenant_id, user.role_id):
        return [p.name for p in (user.role_obj.permissions or [])]
    rows = (
        db.query(TenantRolePermission)
        .filter(
            TenantRolePermission.tenant_id == user.tenant_id,
            TenantRolePermission.role_id == user.role_id,
        )
        .all()
    )
    if not rows:
        return []
    from Models.role import Permission

    perms = (
        db.query(Permission)
        .filter(Permission.id.in_([row.permission_id for row in rows]))
        .all()
    )
    return [perm.name for perm in perms]


def permission_names_for_role(db: Session, tenant_id: int | None, role) -> list[str]:
    if tenant_id is None or not has_tenant_set(db, tenant_id, role.id):
        return [p.name for p in (role.permissions or [])]
    from Models.role import Permission

    rows = (
        db.query(TenantRolePermission.permission_id)
        .filter(
            TenantRolePermission.tenant_id == tenant_id,
            TenantRolePermission.role_id == role.id,
        )
        .all()
    )
    ids = [row[0] for row in rows]
    if not ids:
        return []
    perms = db.query(Permission).filter(Permission.id.in_(ids)).all()
    return [perm.name for perm in perms]


def permission_ids_for_role(db: Session, tenant_id: int | None, role_id: int) -> list[int]:
    if tenant_id is not None and has_tenant_set(db, tenant_id, role_id):
        rows = (
            db.query(TenantRolePermission.permission_id)
            .filter(
                TenantRolePermission.tenant_id == tenant_id,
                TenantRolePermission.role_id == role_id,
            )
            .all()
        )
        return [row[0] for row in rows]
    rows = (
        db.query(RolePermission.permission_id)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return [row[0] for row in rows]


def copy_global_template(db: Session, tenant_id: int, role_id: int) -> None:
    """Create a hospital copy only when that hospital has never customized the role."""
    if has_tenant_set(db, tenant_id, role_id):
        return
    db.add(TenantRolePermissionState(tenant_id=tenant_id, role_id=role_id))
    for (permission_id,) in (
        db.query(RolePermission.permission_id)
        .filter(RolePermission.role_id == role_id)
        .all()
    ):
        db.add(
            TenantRolePermission(
                tenant_id=tenant_id,
                role_id=role_id,
                permission_id=permission_id,
            )
        )


def ensure_tenant_copies(db: Session, tenant_id: int) -> None:
    from Models.role import Role

    for role in db.query(Role).all():
        copy_global_template(db, tenant_id, role.id)


def replace_tenant_permissions(
    db: Session,
    tenant_id: int,
    role_id: int,
    permission_ids: list[int],
) -> None:
    if not has_tenant_set(db, tenant_id, role_id):
        db.add(TenantRolePermissionState(tenant_id=tenant_id, role_id=role_id))
        db.flush()
    db.query(TenantRolePermission).filter(
        TenantRolePermission.tenant_id == tenant_id,
        TenantRolePermission.role_id == role_id,
    ).delete(synchronize_session=False)
    for permission_id in dict.fromkeys(permission_ids):
        db.add(
            TenantRolePermission(
                tenant_id=tenant_id,
                role_id=role_id,
                permission_id=permission_id,
            )
        )
