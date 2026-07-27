from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import PermissionChecker, get_current_user
from Models.user import User
from Schemas.opd_billing_profile_schema import (
    OpdBillingProfileImageResponse,
    OpdBillingProfileResponse,
    OpdBillingProfileUpdate,
)
from Services import opd_billing_profile_service as service

router = APIRouter(prefix="/opd", tags=["OPD Billing Profile"])


@router.get(
    "/profile",
    response_model=OpdBillingProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_opd_billing_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd_billing_profile:view")),
):
    return service.get_opd_billing_profile(db, current_user)


@router.put(
    "/profile",
    response_model=OpdBillingProfileResponse,
    status_code=status.HTTP_200_OK,
)
def update_opd_billing_profile(
    data: OpdBillingProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd_billing_profile:update")),
):
    return service.update_opd_billing_profile(db, current_user, data)


@router.post(
    "/profile/image",
    response_model=OpdBillingProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def upload_opd_billing_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd_billing_profile:upload_image")),
):
    return service.upload_profile_image(db, current_user, file)


@router.delete(
    "/profile/image",
    response_model=OpdBillingProfileImageResponse,
    status_code=status.HTTP_200_OK,
)
def delete_opd_billing_profile_image(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(PermissionChecker("opd_billing_profile:delete_image")),
):
    return service.delete_profile_image(db, current_user)
