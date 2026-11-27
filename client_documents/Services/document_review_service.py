"""Record review remarks without changing existing status vocabulary."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from Models.legal_case import LegalDocument
from Models.user import User
from client_documents.Models.models import DocumentReviewHistory


def record_review(db: Session, actor: User, document: LegalDocument, new_status: str, remarks: str | None) -> None:
    if document.status == "Verified" and new_status != "Verified":
        pass
    db.add(DocumentReviewHistory(
        document_id=document.id,
        reviewer_id=actor.id,
        previous_status=document.status,
        new_status=new_status,
        remarks=remarks,
        version=int(document.version or 1),
    ))
    if remarks:
        document.review_remarks = remarks
