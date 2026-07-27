from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.pharmacist_profile_schema import (
    PharmacistProfileImageResponse,
    PharmacistProfileResponse,
    PharmacistProfileUpdate,
)
from Services import pharmacist_profile_service as service

router = APIRouter(prefix="/pharmacy", tags=["Pharmacist Profile"])


@router.get(
    "/profile",
    response_model=PharmacistProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_pharmacist_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("pharmacist_profile:view")),
):
    return service.get_pharmacist_profile(db, current_user)


@router.put(
    "/profile",
    response_model=PharmacistProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_pharmacist_profile(
    data: PharmacistProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("pharmacist_profile:update")),
):
    return service.update_pharmacist_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=PharmacistProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_pharmacist_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("pharmacist_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=PharmacistProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_pharmacist_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("pharmacist_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
