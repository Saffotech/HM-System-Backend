from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.manager_profile_schema import (
    ManagerProfileImageResponse,
    ManagerProfileResponse,
    ManagerProfileUpdate,
)
from Services import manager_profile_service as service

router = APIRouter(prefix="/manager", tags=["Admin Profile"])


@router.get(
    "/profile",
    response_model=ManagerProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_manager_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("manager_profile:view")),
):
    return service.get_manager_profile(db, current_user)


@router.put(
    "/profile",
    response_model=ManagerProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_manager_profile(
    data: ManagerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("manager_profile:update")),
):
    return service.update_manager_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=ManagerProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_manager_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("manager_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=ManagerProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_manager_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("manager_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
