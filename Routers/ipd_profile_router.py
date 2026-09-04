from fastapi import APIRouter, Depends, File, UploadFile, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.ipd_profile_schema import (
    IpdProfileImageResponse,
    IpdProfileResponse,
    IpdProfileUpdate,
)
from Services import ipd_audit_service as ipd_audit
from Services import ipd_profile_service as service
from Services.audit_helpers import client_ip, user_agent

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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("ipd_profile:update")),
):
    result = service.update_ipd_profile(db, current_user, data)
    ipd_audit.log_profile_update(
        db,
        actor=current_user,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        result=result,
    )
    return result


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

