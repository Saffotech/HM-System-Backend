from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.legal_finance_profile_schema import (
    LegalFinancePasswordChange,
    LegalFinanceProfileOut,
    LegalFinanceProfileUpdate,
)
from Services import legal_finance_profile_service as service
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/legal-finance/account", tags=["Legal Finance Account"])


@router.get("/profile", response_model=LegalFinanceProfileOut)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal_finance_profile:view")),
):
    return service.get_profile(db, current_user)


@router.patch("/profile", response_model=LegalFinanceProfileOut)
def update_profile(
    data: LegalFinanceProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal_finance_profile:update")),
):
    return service.update_profile(db, current_user, data)


@router.post("/password")
def update_password(
    data: LegalFinancePasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal_finance_profile:update")),
):
    return service.change_password(db, current_user, data)


@router.post("/profile/photo", response_model=LegalFinanceProfileOut)
def upload_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal_finance_profile:upload_image")),
):
    return service.upload_photo(db, current_user, file)


@router.delete("/profile/photo", response_model=LegalFinanceProfileOut)
def remove_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("legal_finance_profile:delete_image")),
):
    return service.delete_photo(db, current_user)
