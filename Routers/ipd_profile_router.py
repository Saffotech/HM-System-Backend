from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.ipd_profile_schema import (
    IpdProfileImageResponse,
    IpdProfileResponse,
    IpdProfileUpdate,
)
from Services import ipd_profile_service as service

router = APIRouter(prefix="/ipd", tags=["IPD Profile"])


@router.get(
    "/profile",
    response_model=IpdProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_ipd_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd_profile:view")),
):
    return service.get_ipd_profile(db, current_user)


@router.put(
    "/profile",
    response_model=IpdProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_ipd_profile(
    data: IpdProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd_profile:update")),
):
    return service.update_ipd_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=IpdProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_ipd_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=IpdProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_ipd_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
