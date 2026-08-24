from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.nurse_profile_schema import (
    NurseProfileImageResponse,
    NurseProfileResponse,
    NurseProfileUpdate,
)
from Services.audit_helpers import client_ip, user_agent
from Services import nurse_audit_service as nurse_audit
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:update")),
):
    result = service.update_nurse_profile(db, current_user, data)
    nurse_audit.log_profile_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    return result


@router.post(
    "/profile/image",
    response_model=NurseProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_nurse_profile_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:upload_image")),
):
    result = service.upload_profile_image(db, current_user, file)
    nurse_audit.log_profile_image_upload(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    return result


@router.delete(
    "/profile/image",
    response_model=NurseProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_nurse_profile_image(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("nurse_profile:delete_image")),
):
    result = service.delete_profile_image(db, current_user)
    nurse_audit.log_profile_image_delete(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    return result
