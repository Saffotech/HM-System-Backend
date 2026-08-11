from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.super_admin_profile_schema import (
    SuperAdminProfileImageResponse,
    SuperAdminProfileResponse,
    SuperAdminProfileUpdate,
)
from Services import super_admin_profile_service as service

router = APIRouter(prefix="/super-admin", tags=["Super Admin Profile"])


@router.get(
    "/profile",
    response_model=SuperAdminProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_super_admin_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("super_admin_profile:view")),
):
    return service.get_super_admin_profile(db, current_user)


@router.put(
    "/profile",
    response_model=SuperAdminProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_super_admin_profile(
    data: SuperAdminProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("super_admin_profile:update")),
):
    return service.update_super_admin_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=SuperAdminProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_super_admin_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("super_admin_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=SuperAdminProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_super_admin_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("super_admin_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
