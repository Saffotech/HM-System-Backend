from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query
)

from sqlalchemy.orm import Session

from database import get_db

from dependencies import (
    get_current_user,
    PermissionChecker
)

from Schemas.nurse_emergency_alert_schema import (
    EmergencyAlertCreate,
    EmergencyAlertResolve,
)

from Services.nurse_emergency_alert_service import (
    create_alert_service,
    get_alerts_service,
    get_alert_detail_service,
    get_alert_summary_service,
    resolve_alert_service,
)

router = APIRouter(
    prefix="/nurse/alerts",
    tags=["Nurse Emergency Alerts"]
)


# ==========================================================
# LIST ALERTS
# ==========================================================

@router.get(
    "",
    dependencies=[
        Depends(
            PermissionChecker(
                "emergency_alerts:view"
            )
        )
    ]
)
def get_alerts(

    status: str | None = Query(
        default="active"
    ),

    severity: str | None = Query(
        default=None
    ),

    alert_type: str | None = Query(
        default=None
    ),

    ward_name: str | None = Query(
        default=None
    ),

    patient_id: int | None = Query(
        default=None
    ),

    patient_uid: str | None = Query(
        default=None
    ),

    assigned_nurse_id: int | None = Query(
        default=None
    ),

    unassigned: bool | None = Query(
        default=None
    ),

    from_date: date | None = Query(
        default=None
    ),

    to_date: date | None = Query(
        default=None
    ),

    search: str | None = Query(
        default=None
    ),

    page: int = Query(
        default=1,
        ge=1
    ),

    limit: int = Query(
        default=20,
        ge=1,
        le=100
    ),

    allocated_only: bool = Query(
        default=False,
        description="If true, only alerts for patients on beds allocated to the current nurse.",
    ),

    db: Session = Depends(
        get_db
    ),

    current_user=Depends(
        get_current_user
    )
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
        unassigned=unassigned,
        from_date=from_date,
        to_date=to_date,
        search=search,
        page=page,
        limit=limit,
        allocated_only=allocated_only,
        allocation_nurse_id=current_user.id if allocated_only else None,
    )


# ==========================================================
# DASHBOARD SUMMARY
# ==========================================================

@router.get(
    "/summary",
    dependencies=[
        Depends(
            PermissionChecker(
                "emergency_alerts:view"
            )
        )
    ]
)
def get_alert_summary(

    allocated_only: bool = Query(
        default=False,
        description="If true, summary counts only alerts for patients on beds allocated to the current nurse.",
    ),

    db: Session = Depends(
        get_db
    ),

    current_user=Depends(
        get_current_user
    )
):

    return get_alert_summary_service(
        db,
        allocated_only=allocated_only,
        allocation_nurse_id=current_user.id if allocated_only else None,
    )


# ==========================================================
# CREATE ALERT
# ==========================================================

@router.post(
    "",
    dependencies=[
        Depends(
            PermissionChecker(
                "emergency_alerts:create"
            )
        )
    ]
)
def create_alert(

    alert_data: EmergencyAlertCreate,

    db: Session = Depends(
        get_db
    ),

    current_user=Depends(
        get_current_user
    )
):

    return create_alert_service(
        db=db,
        alert_data=alert_data,
        nurse_id=current_user.id
    )


# ==========================================================
# ALERT DETAIL
# ==========================================================

@router.get(
    "/{alert_id}",
    dependencies=[
        Depends(
            PermissionChecker(
                "emergency_alerts:view"
            )
        )
    ]
)
def get_alert_detail(

    alert_id: int,

    db: Session = Depends(
        get_db
    ),

    current_user=Depends(
        get_current_user
    )
):

    return get_alert_detail_service(
        db=db,
        alert_id=alert_id
    )


# ==========================================================
# RESOLVE ALERT
# ==========================================================

@router.put(
    "/{alert_id}/resolve",
    dependencies=[
        Depends(
            PermissionChecker(
                "emergency_alerts:update"
            )
        )
    ]
)
def resolve_alert(

    alert_id: int,

    resolve_data: EmergencyAlertResolve,

    db: Session = Depends(
        get_db
    ),

    current_user=Depends(
        get_current_user
    )
):

    return resolve_alert_service(
        db=db,
        alert_id=alert_id,
        resolve_data=resolve_data,
        nurse_id=current_user.id
    )