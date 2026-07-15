from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.receptionist_profile_schema import (
    ReceptionistProfileImageResponse,
    ReceptionistProfileResponse,
    ReceptionistProfileUpdate,
)
from Services import receptionist_profile_service as service

router = APIRouter(prefix="/receptionist", tags=["Receptionist Profile"])


@router.get(
    "/profile",
    response_model=ReceptionistProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_receptionist_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("receptionist_profile:view")),
):
    return service.get_receptionist_profile(db, current_user)


@router.put(
    "/profile",
    response_model=ReceptionistProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_receptionist_profile(
    data: ReceptionistProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("receptionist_profile:update")),
):
    return service.update_receptionist_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=ReceptionistProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_receptionist_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("receptionist_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=ReceptionistProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_receptionist_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("receptionist_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
