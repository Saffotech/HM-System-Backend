from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from Models.user import User
from Schemas.crm_profile_schema import CrmPasswordChange, CrmProfileOut, CrmProfileUpdate
from Services import crm_profile_service as service
from database import get_db
from dependencies import PermissionChecker, get_current_user

router = APIRouter(prefix="/crm/account", tags=["CRM Account"])


@router.get("/profile", response_model=CrmProfileOut)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("crm_profile:view")),
):
    return service.get_profile(db, current_user)


@router.patch("/profile", response_model=CrmProfileOut)
def update_profile(
    data: CrmProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("crm_profile:update")),
):
    return service.update_profile(db, current_user, data)


@router.post("/password")
def update_password(
    data: CrmPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("crm_profile:update")),
):
    return service.change_password(db, current_user, data)


@router.post("/profile/photo", response_model=CrmProfileOut)
def upload_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("crm_profile:upload_image")),
):
    return service.upload_photo(db, current_user, file)


@router.delete("/profile/photo", response_model=CrmProfileOut)
def remove_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("crm_profile:delete_image")),
):
    return service.delete_photo(db, current_user)
