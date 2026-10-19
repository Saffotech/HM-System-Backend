"""Stamp and filter hospital-owned rows from the logged-in user's tenant_id."""
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from Models.audit_log import AuditLog
from Models.tenant import TenantScoped
from Models.user import User


@event.listens_for(Session, "before_flush")
def _assign_tenant_id(session, flush_context, instances):
    tenant_id = session.info.get("tenant_id")
    if not tenant_id:
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped) and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tenant_id


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    if execute_state.execution_options.get("include_all_tenants"):
        return
    tenant_id = execute_state.session.info.get("tenant_id")
    platform_user = execute_state.session.info.get("platform_user")
    if not tenant_id:
        if not platform_user:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScoped,
                lambda cls: cls.tenant_id == -1,
                include_aliases=True,
            )
        )
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        ),
        with_loader_criteria(
            User,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        ),
        with_loader_criteria(
            AuditLog,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        ),
    )
