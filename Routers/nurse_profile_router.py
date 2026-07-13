from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_profile_schema import (
    NurseProfileImageResponse,
    NurseProfileResponse,
    NurseProfileUpdate,
)
from Services import nurse_profile_service as service

router = APIRouter(prefix="/nurse", tags=["Nurse Profile"])


@router.get(
    "/profile",
    response_model=NurseProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_nurse_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:view")),
):
    return service.get_nurse_profile(db, current_user)


@router.put(
    "/profile",
    response_model=NurseProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_nurse_profile(
    data: NurseProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:update")),
):
    return service.update_nurse_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=NurseProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_nurse_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=NurseProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_nurse_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
