from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, PermissionChecker
from Schemas.nurse_emergency_alert_schema import (
    EmergencyAlertCreate,
    EmergencyAlertAssign,
    EmergencyAlertResolve,
    EmergencyAlertEscalate,
    EmergencyAlertListResponse,
    EmergencyAlertSummaryResponse,
    EmergencyAlertCreateResponse,
    EmergencyAlertDetailResponse,
    EmergencyAlertActionResponse,
)
from Services.nurse_emergency_alert_service import (
    create_alert_service,
    get_alerts_service,
    get_alert_detail_service,
    get_alert_summary_service,
    assign_alert_service,
    resolve_alert_service,
    escalate_alert_service,
)

router = APIRouter(prefix="/nurse/alerts", tags=["Nurse Emergency Alerts"])


@router.get(
    "",
    response_model=EmergencyAlertListResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:view"))],
)
def get_alerts(
    status: str | None = Query(default="active"),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    ward_name: str | None = Query(default=None),
    patient_id: int | None = Query(default=None),
    patient_uid: str | None = Query(default=None),
    assigned_nurse_id: int | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_alerts_service(
        db=db,
        status=status,
        severity=severity,
        alert_type=alert_type,
        ward_name=ward_name,
        patient_id=patient_id,
        patient_uid=patient_uid,
        assigned_nurse_id=assigned_nurse_id,
        from_date=from_date,
        to_date=to_date,
        search=search,
        page=page,
        limit=limit,
    )


@router.get(
    "/summary",
    response_model=EmergencyAlertSummaryResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:view"))],
)
def get_alert_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_alert_summary_service(db)


@router.post(
    "",
    response_model=EmergencyAlertCreateResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:create"))],
)
def create_alert(
    alert_data: EmergencyAlertCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return create_alert_service(
        db=db,
        alert_data=alert_data,
        nurse_id=current_user.id,
    )


@router.get(
    "/{alert_id}",
    response_model=EmergencyAlertDetailResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:view"))],
)
def get_alert_detail(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_alert_detail_service(db=db, alert_id=alert_id)


@router.put(
    "/{alert_id}/assign",
    response_model=EmergencyAlertActionResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:update"))],
)
def assign_alert(
    alert_id: int,
    assign_data: EmergencyAlertAssign,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return assign_alert_service(
        db=db,
        alert_id=alert_id,
        assign_data=assign_data,
        nurse_id=current_user.id,
    )


@router.put(
    "/{alert_id}/resolve",
    response_model=EmergencyAlertActionResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:update"))],
)
def resolve_alert(
    alert_id: int,
    resolve_data: EmergencyAlertResolve,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return resolve_alert_service(
        db=db,
        alert_id=alert_id,
        resolve_data=resolve_data,
        nurse_id=current_user.id,
    )


@router.put(
    "/{alert_id}/escalate",
    response_model=EmergencyAlertActionResponse,
    dependencies=[Depends(PermissionChecker("nurse_alerts:escalate"))],
)
def escalate_alert(
    alert_id: int,
    escalate_data: EmergencyAlertEscalate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return escalate_alert_service(
        db=db,
        alert_id=alert_id,
        escalate_data=escalate_data,
        nurse_id=current_user.id,
    )
