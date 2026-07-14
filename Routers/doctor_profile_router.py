from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.doctor_profile_schema import (
    DoctorProfileImageResponse,
    DoctorProfileResponse,
    DoctorProfileUpdate,
)
from Services import doctor_profile_service as service

router = APIRouter(prefix="/doctor", tags=["Doctor Profile"])


@router.get(
    "/profile",
    response_model=DoctorProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_doctor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_profile:view")),
):
    return service.get_doctor_profile(db, current_user)


@router.put(
    "/profile",
    response_model=DoctorProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_doctor_profile(
    data: DoctorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_profile:update")),
):
    return service.update_doctor_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=DoctorProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_doctor_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=DoctorProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_doctor_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("doctor_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
