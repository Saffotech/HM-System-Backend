from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.accountant_profile_schema import (
    AccountantPasswordChange,
    AccountantProfileOut,
    AccountantProfileUpdate,
)
from Services import accountant_profile_service as service
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/platform/account", tags=["Accountant Account"])


@router.get("/profile", response_model=AccountantProfileOut)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("accountant_profile:view")),
):
    return service.get_profile(db, current_user)


@router.patch("/profile", response_model=AccountantProfileOut)
def update_profile(
    data: AccountantProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("accountant_profile:update")),
):
    return service.update_profile(db, current_user, data)


@router.post("/password")
def update_password(
    data: AccountantPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("accountant_profile:update")),
):
    return service.change_password(db, current_user, data)


@router.post("/profile/photo", response_model=AccountantProfileOut)
def upload_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("accountant_profile:upload_image")),
):
    return service.upload_photo(db, current_user, file)


@router.delete("/profile/photo", response_model=AccountantProfileOut)
def remove_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("accountant_profile:delete_image")),
):
    return service.delete_photo(db, current_user)
