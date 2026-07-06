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

    # clear existing and reassign
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for perm_id in data.permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))
    db.commit()
    audit_service.log_event(
        db,
        actor=current_user,
        action="role.permissions_update",
        resource_type="role",
        resource_id=role.id,
        summary=f"Updated permissions for role {role.name}",
        details={"role": role.name, "permission_ids": data.permission_ids},
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