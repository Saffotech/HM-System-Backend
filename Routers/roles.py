from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.role import Role, Permission, RolePermission
from Schemas.schemas import RoleCreate, PermissionCreate, AssignPermissions
from Models.user import User
from dependencies import PermissionChecker, get_current_user
from Services import audit_service

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
    from Services.admin_edit_policy import apply_module_locks_to_permission_ids
    from Services import opd_settings_service

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permission_ids = list(data.permission_ids or [])
    caller_role = (
        (current_user.role_obj.name or "").strip().lower()
        if current_user.role_obj
        else ""
    )
    if caller_role != "super_admin":
        all_perms = db.query(Permission).all()
        id_by_name = {p.name: p.id for p in all_perms}
        name_by_id = {p.id: p.name for p in all_perms}
        current_ids = [p.id for p in (role.permissions or [])]
        locks = opd_settings_service.get_admin_edit_controls(db)
        permission_ids = apply_module_locks_to_permission_ids(
            locks=locks,
            role_name=role.name or "",
            current_permission_ids=current_ids,
            current_name_by_id=name_by_id,
            requested_permission_ids=permission_ids,
            permission_id_by_name=id_by_name,
        )

    # clear existing and reassign
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for perm_id in permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))
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
            "permissions": [p.name for p in r.permissions]
        }
        for r in roles
    ]