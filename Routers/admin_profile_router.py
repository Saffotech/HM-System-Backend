from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.admin_profile_schema import (
    AdminProfileImageResponse,
    AdminProfileResponse,
    AdminProfileUpdate,
)
from Services import admin_profile_service as service

router = APIRouter(prefix="/admin", tags=["Admin Profile"])


@router.get(
    "/profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_admin_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("admin_profile:view")),
):
    return service.get_admin_profile(db, current_user)


@router.put(
    "/profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_admin_profile(
    data: AdminProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("admin_profile:update")),
):
    return service.update_admin_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=AdminProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_admin_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("admin_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=AdminProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_admin_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("admin_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
