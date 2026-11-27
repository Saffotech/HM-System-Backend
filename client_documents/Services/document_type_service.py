"""Global document master. Required flags do not change Legal or Accounts gates."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.user import User
from client_documents.Models.models import DocumentType

UPLOADS = (
    ("HOSPITAL_REGISTRATION", "Hospital Registration", "Upload the hospital registration certificate.", 1, "HOSPITAL_REGISTRATION_REVIEWED"),
    ("ENTITY_REGISTRATION", "Entity Registration", "Upload entity registration.", 2, "LEGAL_ENTITY_IDENTITY"),
    ("AUTHORIZED_REPRESENTATIVE", "Authorized Representative", "Upload authorized representative proof.", 3, "AUTHORIZED_SIGNATORY"),
    ("TAX_GST_DETAILS", "Tax / GST Details", "Upload tax or GST details.", 4, None),
    ("HOSPITAL_LICENSE", "Hospital License", "Upload the hospital license.", 5, "LICENSES_CHECKED"),
    ("SERVICE_AGREEMENT", "Service Agreement", "Upload the service agreement.", 6, "AGREEMENT_TERMS"),
)
CHECKLIST = (
    ("LEGAL_ENTITY_IDENTITY", "Legal entity identity verified", 1),
    ("HOSPITAL_REGISTRATION_REVIEWED", "Hospital registration documents reviewed", 2),
    ("HOSPITAL_ADDRESS_CHECKED", "Hospital address checked", 3),
    ("AUTHORIZED_SIGNATORY", "Authorized signatory verified", 4),
    ("LICENSES_CHECKED", "Relevant licenses checked (where applicable)", 5),
    ("AGREEMENT_TERMS", "Agreement and data protection terms reviewed", 6),
    ("CONTRACT_SIGNING", "Contract signing requirements checked", 7),
)
DEFAULT_TYPES = ".pdf,.jpg,.jpeg,.png,.webp"
APP_MAX_MB = 5


def seed_document_types(db: Session) -> None:
    existing = {row.code: row for row in db.query(DocumentType).all()}
    for code, name, description, order, link in UPLOADS:
        if code in existing:
            continue
        db.add(DocumentType(
            code=code,
            name=name,
            description=description,
            requirement_type="CLIENT_UPLOAD",
            is_required=True,
            is_active=True,
            allowed_file_types=DEFAULT_TYPES,
            max_file_size_mb=APP_MAX_MB,
            display_order=order,
            linked_checklist_code=link,
        ))
    for code, name, order in CHECKLIST:
        if code in existing:
            continue
        db.add(DocumentType(
            code=code,
            name=name,
            description=None,
            requirement_type="INTERNAL_CHECKLIST",
            is_required=True,
            is_active=True,
            allowed_file_types=DEFAULT_TYPES,
            max_file_size_mb=APP_MAX_MB,
            display_order=order,
        ))
    db.flush()


def active_uploads(db: Session) -> list[DocumentType]:
    return (
        db.query(DocumentType)
        .filter(DocumentType.requirement_type == "CLIENT_UPLOAD", DocumentType.is_active.is_(True))
        .order_by(DocumentType.display_order.asc(), DocumentType.id.asc())
        .all()
    )


def by_name(db: Session, name: str) -> DocumentType | None:
    return (
        db.query(DocumentType)
        .filter(DocumentType.name == name, DocumentType.requirement_type == "CLIENT_UPLOAD", DocumentType.is_active.is_(True))
        .first()
    )


def allowed_suffixes(row: DocumentType) -> set[str]:
    return {part.strip().lower() for part in (row.allowed_file_types or "").split(",") if part.strip()}


def create_type(db: Session, actor: User, data) -> DocumentType:
    if db.query(DocumentType).filter(DocumentType.code == data.code).first():
        raise HTTPException(status_code=409, detail="Document code already exists.")
    if data.max_file_size_mb > APP_MAX_MB:
        raise HTTPException(status_code=422, detail="File size exceeds the application limit.")
    suffixes = {item.lower() for item in data.allowed_file_types}
    if not suffixes.issubset({".pdf", ".jpg", ".jpeg", ".png", ".webp"}):
        raise HTTPException(status_code=422, detail="Unsupported file type.")
    row = DocumentType(
        code=data.code.strip().upper(),
        name=data.name.strip(),
        description=data.description,
        requirement_type=data.requirement_type,
        is_required=data.is_required,
        is_active=data.is_active,
        allowed_file_types=",".join(sorted(suffixes)),
        max_file_size_mb=data.max_file_size_mb,
        display_order=data.display_order,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_type(db: Session, actor: User, type_id: int, data) -> DocumentType:
    row = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document type not found")
    payload = data.model_dump(exclude_unset=True)
    if "code" in payload or "requirement_type" in payload:
        raise HTTPException(status_code=409, detail="Code and requirement type cannot change.")
    if "max_file_size_mb" in payload and payload["max_file_size_mb"] > APP_MAX_MB:
        raise HTTPException(status_code=422, detail="File size exceeds the application limit.")
    if "allowed_file_types" in payload:
        suffixes = {item.lower() for item in payload["allowed_file_types"]}
        if not suffixes.issubset({".pdf", ".jpg", ".jpeg", ".png", ".webp"}):
            raise HTTPException(status_code=422, detail="Unsupported file type.")
        payload["allowed_file_types"] = ",".join(sorted(suffixes))
    for key, value in payload.items():
        setattr(row, key, value)
    row.updated_by = actor.id
    db.commit()
    db.refresh(row)
    return row


def set_status(db: Session, actor: User, type_id: int, is_active: bool) -> DocumentType:
    row = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document type not found")
    row.is_active = is_active
    row.updated_by = actor.id
    db.commit()
    db.refresh(row)
    return row
