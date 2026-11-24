from sqlalchemy import Column, Index, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class Role(Base):
    __tablename__ = "roles"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at  = Column(DateTime(timezone=True),
                    default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    # relationship to permissions only
    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles"
    )
    # ← REMOVE users relationship from here


class Permission(Base):
    __tablename__ = "permissions"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)

    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id       = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)


class TenantRolePermissionState(Base):
    """Marks that a hospital has its own permission set for a global role template."""

    __tablename__ = "tenant_role_permission_state"

    tenant_id = Column(Integer, ForeignKey("tenants.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)


class TenantRolePermission(Base):
    """Hospital-specific grants. Empty set is valid once a state row exists."""

    __tablename__ = "tenant_role_permissions"

    tenant_id = Column(Integer, ForeignKey("tenants.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)
    __table_args__ = (
        Index("ix_tenant_role_permissions_role", "tenant_id", "role_id"),
    )