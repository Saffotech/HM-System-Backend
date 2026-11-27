from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Models.user import User
from Services.audit_service import log_event
from Services.role_policy import caller_role_name
from client_documents.Schemas.document_type_schema import (
    DocumentTypeCreate,
    DocumentTypeOut,
    DocumentTypeStatus,
    DocumentTypeUpdate,
)
from client_documents.Services import document_type_service as service
from client_documents.dependencies import require_client_documents_enabled
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/document-types", tags=["Document Master"])


def _admin(user: User) -> None:
    if caller_role_name(user) != "platform_admin" or user.tenant_id is not None:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only a platform admin can manage document types.")


@router.get("", response_model=list[DocumentTypeOut])
def list_types(
    requirement_type: str | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: bool = Depends(PermissionChecker("document_types:view")),
):
    require_client_documents_enabled()
    service.seed_document_types(db)
    db.commit()
    rows = db.query(service.DocumentType).order_by(service.DocumentType.display_order.asc()).all()
    if requirement_type:
        rows = [row for row in rows if row.requirement_type == requirement_type]
    if active is not None:
        rows = [row for row in rows if row.is_active is active]
    start = (page - 1) * page_size
    return [DocumentTypeOut.from_row(row) for row in rows[start:start + page_size]]


@router.get("/{type_id}", response_model=DocumentTypeOut)
def read_type(
    type_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(PermissionChecker("document_types:view")),
):
    require_client_documents_enabled()
    row = db.query(service.DocumentType).filter(service.DocumentType.id == type_id).first()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document type not found")
    return DocumentTypeOut.from_row(row)


@router.post("", response_model=DocumentTypeOut, status_code=201)
def create_type(
    data: DocumentTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("document_types:manage")),
):
    require_client_documents_enabled()
    _admin(current_user)
    if data.requirement_type not in ("CLIENT_UPLOAD", "INTERNAL_CHECKLIST"):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Unknown requirement type.")
    row = service.create_type(db, current_user, data)
    log_event(db, actor=current_user, action="document_type.create", resource_type="document_type", resource_id=row.id, summary=f"Created document type {row.code}")
    return DocumentTypeOut.from_row(row)


@router.patch("/{type_id}", response_model=DocumentTypeOut)
def update_type(
    type_id: int,
    data: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("document_types:manage")),
):
    require_client_documents_enabled()
    _admin(current_user)
    row = service.update_type(db, current_user, type_id, data)
    log_event(db, actor=current_user, action="document_type.update", resource_type="document_type", resource_id=row.id, summary=f"Updated document type {row.code}")
    return DocumentTypeOut.from_row(row)


@router.patch("/{type_id}/status", response_model=DocumentTypeOut)
def update_status(
    type_id: int,
    data: DocumentTypeStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("document_types:manage")),
):
    require_client_documents_enabled()
    _admin(current_user)
    row = service.set_status(db, current_user, type_id, data.is_active)
    log_event(db, actor=current_user, action="document_type.status", resource_type="document_type", resource_id=row.id, summary=f"Set {row.code} active={row.is_active}")
    return DocumentTypeOut.from_row(row)
