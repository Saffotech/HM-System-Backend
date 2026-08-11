from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.lab_technician_profile_schema import (
    LabTechnicianProfileImageResponse,
    LabTechnicianProfileResponse,
    LabTechnicianProfileUpdate,
)
from Services import lab_technician_profile_service as service

router = APIRouter(prefix="/lab", tags=["Lab Technician Profile"])


@router.get(
    "/profile",
    response_model=LabTechnicianProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_lab_technician_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_technician_profile:view")),
):
    return service.get_lab_technician_profile(db, current_user)


@router.put(
    "/profile",
    response_model=LabTechnicianProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_lab_technician_profile(
    data: LabTechnicianProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_technician_profile:update")),
):
    return service.update_lab_technician_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=LabTechnicianProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_lab_technician_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_technician_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=LabTechnicianProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_lab_technician_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("lab_technician_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
