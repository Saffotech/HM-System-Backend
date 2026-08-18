"""Audit logging for lab technician actions (Super Admin reads via GET /super-admin/audit)."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from Models.user import User
from Services.audit_helpers import safe_log_event

RESOURCE_TYPE = "lab_order"


def _base_order_details(
    *,
    order_id: int,
    patient_uid: Optional[str] = None,
    test_name: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"order_id": order_id}
    if patient_uid:
        details["patient_uid"] = patient_uid
    if test_name:
        details["test_name"] = test_name
    if extra:
        details.update(extra)
    return details


def log_sample_collected(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    patient_uid: str | None,
    test_name: str | None,
    previous_status: str,
    new_status: str,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.sample_collected",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab sample collected for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "previous_status": previous_status,
                "new_status": new_status,
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_report_upload(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    report_id: int,
    patient_uid: str | None,
    test_name: str | None,
    parameter_count: int,
    has_file_ref: bool,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.report.upload",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab report uploaded for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "report_id": report_id,
                "parameter_count": parameter_count,
                "has_file_ref": has_file_ref,
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_report_file_upload(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    report_id: int,
    patient_uid: str | None,
    test_name: str | None,
    file_name: str | None,
    file_type: str | None,
    file_size: int | None,
    replaced_previous_file: bool,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.report.file_upload",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab report file uploaded for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "report_id": report_id,
                "file_name": file_name,
                "file_type": file_type,
                "file_size": file_size,
                "replaced_previous_file": replaced_previous_file,
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_complete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    patient_uid: str | None,
    test_name: str | None,
    previous_status: str,
    new_status: str,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.complete",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab test completed for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "previous_status": previous_status,
                "new_status": new_status,
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_report_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    report_id: int,
    patient_uid: str | None = None,
    test_name: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.report.view",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab technician viewed report {report_id} for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "report_id": report_id,
                "access_mode": "metadata",
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_report_file_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    order_id: int,
    report_id: int,
    patient_uid: str | None = None,
    test_name: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action="lab.report.file_view",
        resource_type=RESOURCE_TYPE,
        resource_id=order_id,
        summary=f"Lab technician downloaded report file {report_id} for order {order_id}",
        details=_base_order_details(
            order_id=order_id,
            patient_uid=patient_uid,
            test_name=test_name,
            extra={
                "report_id": report_id,
                "access_mode": "file",
            },
        ),
        ip_address=ip_address,
        user_agent=user_agent,
    )
