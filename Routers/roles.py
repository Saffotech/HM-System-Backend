from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.role import Permission, Role, RolePermission
from Schemas.schemas import AssignPermissions, PermissionCreate, RoleCreate
from Models.user import User
from dependencies import PermissionChecker, get_current_user
from Services import audit_service
from Services.admin_edit_policy import (
    apply_module_locks_to_permission_ids,
    normalize_admin_edit,
)
from Services.opd_settings_service import get_settings_row
from Services.tenant_permission_service import (
    permission_ids_for_role,
    permission_names_for_role,
    replace_tenant_permissions,
)

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("/", status_code=201)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roles:create")),
):
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role already exists")
    role = Role(name=data.name, description=data.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    audit_service.log_event(
        db,
        actor=current_user,
        action="role.create",
        resource_type="role",
        resource_id=role.id,
        summary=f"Created role {role.name}",
        details={"name": role.name, "description": data.description},
    )
    return {"message": "Role created", "role_id": role.id, "name": role.name}


@router.post("/permissions", status_code=201)
def create_permission(
    data: PermissionCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(PermissionChecker("roles:create"))
):
    perm = Permission(name=data.name, description=data.description)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return {"message": "Permission created", "permission_id": perm.id}


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roles:view")),
):
    permissions = db.query(Permission).order_by(Permission.name.asc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
        }
        for p in permissions
    ]


@router.post("/{role_id}/permissions")
def assign_permissions(
    role_id: int,
    data: AssignPermissions,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roles:create")),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Hospital context is required")

    requested_ids = list(data.permission_ids or [])
    current_ids = permission_ids_for_role(db, current_user.tenant_id, role_id)
    permissions = db.query(Permission).all()
    id_by_name = {perm.name: perm.id for perm in permissions}
    name_by_id = {perm.id: perm.name for perm in permissions}
    try:
        locks = normalize_admin_edit(
            (get_settings_row(db, current_user.tenant_id).extra or {}).get("admin_edit")
        )
    except HTTPException:
        locks = normalize_admin_edit(None)
    actor_role = (current_user.role_obj.name if current_user.role_obj else "").lower()
    if actor_role != "admin":
        locked_now = set(current_ids)
        proposed = set(requested_ids)
        from Services.admin_edit_policy import locked_permission_names

        protected = locked_permission_names(locks, role.name)
        current_names = {name_by_id.get(pid) for pid in locked_now}
        requested_names = {name_by_id.get(pid) for pid in proposed}
        for name in protected:
            if (name in current_names) != (name in requested_names):
                raise HTTPException(
                    status_code=403,
                    detail=f"This settings section is locked: {name}",
                )
    if actor_role == "admin":
        permission_ids = requested_ids
    else:
        permission_ids = apply_module_locks_to_permission_ids(
            locks=locks,
            role_name=role.name,
            current_permission_ids=current_ids,
            current_name_by_id=name_by_id,
            requested_permission_ids=requested_ids,
            permission_id_by_name=id_by_name,
        )
    replace_tenant_permissions(db, current_user.tenant_id, role_id, permission_ids)
    db.commit()
    audit_service.log_event(
        db,
        actor=current_user,
        action="role.permissions_update",
        resource_type="role",
        resource_id=role.id,
        summary=f"Updated permissions for role {role.name}",
        details={"role": role.name, "permission_ids": permission_ids},
    )
    return {"message": "Permissions assigned successfully"}


@router.get("/")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("roles:view")),
):
    roles = db.query(Role).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "permissions": permission_names_for_role(db, current_user.tenant_id, r)
        }
        for r in roles
    ]