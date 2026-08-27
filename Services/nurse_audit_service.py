"""Audit logging for nurse-module actions (Super Admin reads via GET /super-admin/audit)."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from Models.user import User
from Services.audit_helpers import safe_log_event


def _attr(obj: Any, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _log(
    db: Session,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    summary: str,
    details: Optional[dict[str, Any]] = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    safe_log_event(
        db,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        summary=summary,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_vitals_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    vital_id = _attr(result, "id")
    patient_id = _attr(result, "patient_id")
    _log(
        db,
        actor=actor,
        action="nurse.vitals.create",
        resource_type="patient_vitals",
        resource_id=vital_id,
        summary=f"Nurse recorded vitals {vital_id} for patient {patient_id}",
        details={"vital_id": vital_id, "patient_id": patient_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_vitals_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    vital_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.vitals.update",
        resource_type="patient_vitals",
        resource_id=_attr(result, "id") or vital_id,
        summary=f"Nurse updated vitals {vital_id}",
        details={
            "vital_id": _attr(result, "id") or vital_id,
            "patient_id": _attr(result, "patient_id"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_vitals_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    vital_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.vitals.view",
        resource_type="patient_vitals",
        resource_id=vital_id,
        summary=f"Nurse viewed vitals {vital_id}",
        details={"vital_id": vital_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_notes_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    note_id = _attr(result, "id")
    patient_id = _attr(result, "patient_id")
    _log(
        db,
        actor=actor,
        action="nurse.notes.create",
        resource_type="nursing_note",
        resource_id=note_id,
        summary=f"Nurse created note {note_id} for patient {patient_id}",
        details={"note_id": note_id, "patient_id": patient_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_notes_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    note_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.notes.update",
        resource_type="nursing_note",
        resource_id=_attr(result, "id") or note_id,
        summary=f"Nurse updated note {note_id}",
        details={
            "note_id": _attr(result, "id") or note_id,
            "patient_id": _attr(result, "patient_id"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_notes_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    note_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.notes.view",
        resource_type="nursing_note",
        resource_id=note_id,
        summary=f"Nurse viewed note {note_id}",
        details={"note_id": note_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_medication_administer(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    admin_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="nurse.medication.administer",
        resource_type="medication_administration",
        resource_id=admin_id,
        summary=f"Nurse administered medication {admin_id}",
        details={
            "administration_id": admin_id,
            "patient_id": _attr(result, "patient_id"),
            "medicine_name": _attr(result, "medicine_name"),
            "status": str(_attr(result, "status") or ""),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_medication_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    administration_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.medication.update",
        resource_type="medication_administration",
        resource_id=_attr(result, "id") or administration_id,
        summary=f"Nurse updated medication administration {administration_id}",
        details={
            "administration_id": _attr(result, "id") or administration_id,
            "patient_id": _attr(result, "patient_id"),
            "status": str(_attr(result, "status") or ""),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_medication_patient_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.medication.view",
        resource_type="patient",
        resource_id=patient_id,
        summary=f"Nurse viewed medications for patient {patient_id}",
        details={"patient_id": patient_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_handover_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    handover_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="nurse.handover.create",
        resource_type="shift_handover",
        resource_id=handover_id,
        summary=f"Nurse created handover {handover_id}",
        details={
            "handover_id": handover_id,
            "handover_uid": _attr(result, "handover_uid"),
            "ward_name": _attr(result, "ward_name"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_handover_patients_add(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    handover_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.handover.patients_add",
        resource_type="shift_handover",
        resource_id=handover_id,
        summary=f"Nurse added patients to handover {handover_id}",
        details={
            "handover_id": handover_id,
            "count": _attr(result, "count"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_handover_patient_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    patient_summary_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.handover.patient_delete",
        resource_type="shift_handover_patient",
        resource_id=patient_summary_id,
        summary=f"Nurse removed patient summary {patient_summary_id} from handover",
        details={"patient_summary_id": patient_summary_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_handover_submit(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    handover_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.handover.submit",
        resource_type="shift_handover",
        resource_id=_attr(result, "handover_id") or handover_id,
        summary=f"Nurse submitted handover {handover_id}",
        details={
            "handover_id": _attr(result, "handover_id") or handover_id,
            "handover_uid": _attr(result, "handover_uid"),
            "status": str(_attr(result, "status") or ""),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_handover_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    handover_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.handover.view",
        resource_type="shift_handover",
        resource_id=handover_id,
        summary=f"Nurse viewed handover {handover_id}",
        details={"handover_id": handover_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_visit_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    visit_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="nurse.doctor_visit.create",
        resource_type="nurse_doctor_visit",
        resource_id=visit_id,
        summary=f"Nurse logged doctor visit {visit_id}",
        details={
            "visit_id": visit_id,
            "patient_id": _attr(result, "patient_id"),
            "doctor_id": _attr(result, "doctor_id"),
            "doctor_name": _attr(result, "doctor_name"),
            "department_id": _attr(result, "department_id"),
            "department_name": _attr(result, "department_name"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_visit_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.doctor_visit.update",
        resource_type="nurse_doctor_visit",
        resource_id=_attr(result, "id") or visit_id,
        summary=f"Nurse updated doctor visit {visit_id}",
        details={
            "visit_id": _attr(result, "id") or visit_id,
            "patient_id": _attr(result, "patient_id"),
            "doctor_id": _attr(result, "doctor_id"),
            "department_id": _attr(result, "department_id"),
            "department_name": _attr(result, "department_name"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_doctor_visit_void(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    void_reason: str | None,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.doctor_visit.void",
        resource_type="nurse_doctor_visit",
        resource_id=visit_id,
        summary=f"Nurse voided doctor visit {visit_id}",
        details={"visit_id": visit_id, "void_reason": void_reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_other_visit_create(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    result: Any,
) -> None:
    visit_id = _attr(result, "id")
    _log(
        db,
        actor=actor,
        action="nurse.other_visit.create",
        resource_type="nurse_other_visit",
        resource_id=visit_id,
        summary=f"Nurse logged other visit {visit_id}",
        details={
            "visit_id": visit_id,
            "patient_id": _attr(result, "patient_id"),
            "department_id": _attr(result, "department_id"),
            "person_name": _attr(result, "person_name"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_other_visit_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    result: Any,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.other_visit.update",
        resource_type="nurse_other_visit",
        resource_id=_attr(result, "id") or visit_id,
        summary=f"Nurse updated other visit {visit_id}",
        details={
            "visit_id": _attr(result, "id") or visit_id,
            "patient_id": _attr(result, "patient_id"),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_other_visit_void(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    visit_id: int,
    void_reason: str | None,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.other_visit.void",
        resource_type="nurse_other_visit",
        resource_id=visit_id,
        summary=f"Nurse voided other visit {visit_id}",
        details={"visit_id": visit_id, "void_reason": void_reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_profile_update(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    fields: list[str],
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.profile.update",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Nurse {actor.id} updated profile",
        details={"fields": fields},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_profile_image_upload(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.profile.image_upload",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Nurse {actor.id} uploaded profile image",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_profile_image_delete(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.profile.image_delete",
        resource_type="user",
        resource_id=actor.id,
        summary=f"Nurse {actor.id} deleted profile image",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_report_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    report_id: int,
    order_id: int | None = None,
    patient_id: int | None = None,
    test_name: str | None = None,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.lab_report.view",
        resource_type="lab_result",
        resource_id=report_id,
        summary=f"Nurse viewed lab report {report_id}",
        details={
            "report_id": report_id,
            "order_id": order_id,
            "patient_id": patient_id,
            "test_name": test_name,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_lab_report_file_view(
    db: Session,
    *,
    actor: User,
    ip_address: str | None,
    user_agent: str | None,
    report_id: int,
) -> None:
    _log(
        db,
        actor=actor,
        action="nurse.lab_report.file_view",
        resource_type="lab_result",
        resource_id=report_id,
        summary=f"Nurse downloaded lab report file {report_id}",
        details={"report_id": report_id, "access_mode": "file"},
        ip_address=ip_address,
        user_agent=user_agent,
    )
