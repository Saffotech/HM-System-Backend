from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from Models.nurse_patient_vitals import PatientVitals, VitalStatus
from Models.patient import Patient
from Schemas.nurse_schema import VitalCreate, VitalUpdate, VitalResponse
from Services import nurse_helpers as nh
from Services.nurse_emergency_alert_triggers import process_vital_alerts


def _vital_query(db: Session):
    return db.query(PatientVitals).options(
        joinedload(PatientVitals.patient),
        joinedload(PatientVitals.nurse),
    )


def _serialize_vital(
    vital: PatientVitals,
    *,
    bed_number: str | None = None,
) -> VitalResponse:
    patient = vital.patient
    nurse = vital.nurse
    return VitalResponse(
        id=vital.id,
        appointment_id=vital.appointment_id,
        patient_id=vital.patient_id,
        patient_uid=patient.patient_uid if patient else None,
        patient_name=nh.patient_display_name(patient),
        bed_number=bed_number,
        recorded_by=vital.recorded_by,
        recorded_by_name=nh.user_display_name(nurse),
        temperature=vital.temperature,
        blood_pressure=vital.blood_pressure,
        heart_rate=vital.heart_rate,
        respiratory_rate=vital.respiratory_rate,
        oxygen_saturation=vital.oxygen_saturation,
        blood_sugar=vital.blood_sugar,
        weight=vital.weight,
        pain_level=vital.pain_level,
        observation_notes=vital.observation_notes,
        status=vital.status.value if vital.status else None,
        recorded_at=vital.recorded_at,
    )


def _serialize_vitals(db: Session, vitals: list[PatientVitals]) -> list[VitalResponse]:
    if not vitals:
        return []
    beds = nh.occupied_beds_map(db, {v.patient_id for v in vitals})
    return [
        _serialize_vital(
            vital,
            bed_number=(
                beds[vital.patient_id].bed_number
                if vital.patient_id in beds
                else None
            ),
        )
        for vital in vitals
    ]


def create_vital_service(
    db: Session,
    vital_data: VitalCreate,
    nurse_id: int,
):
    patient, appointment = nh.resolve_patient_and_appointment(
        db,
        appointment_id=vital_data.appointment_id,
        patient_id=vital_data.patient_id,
    )

    if appointment is not None:
        existing_vital = (
            db.query(PatientVitals)
            .filter(PatientVitals.appointment_id == appointment.id)
            .first()
        )
        if existing_vital:
            raise HTTPException(
                status_code=400,
                detail="Vitals already recorded for this appointment",
            )
    else:
        existing_today = (
            db.query(PatientVitals)
            .filter(
                PatientVitals.patient_id == patient.id,
                PatientVitals.appointment_id.is_(None),
                PatientVitals.recorded_at >= nh.today_start_ist(),
            )
            .first()
        )
        if existing_today:
            raise HTTPException(
                status_code=400,
                detail="Vitals already recorded today for this IPD patient",
            )

    try:
        vital = PatientVitals(
            appointment_id=appointment.id if appointment else None,
            patient_id=patient.id,
            recorded_by=nurse_id,
            created_by=nurse_id,
            updated_by=nurse_id,
            status=VitalStatus.RECORDED,
            temperature=vital_data.temperature,
            blood_pressure=vital_data.blood_pressure,
            heart_rate=vital_data.heart_rate,
            respiratory_rate=vital_data.respiratory_rate,
            oxygen_saturation=vital_data.oxygen_saturation,
            blood_sugar=vital_data.blood_sugar,
            weight=vital_data.weight,
            pain_level=vital_data.pain_level,
            observation_notes=vital_data.observation_notes,
        )
        db.add(vital)
        db.commit()
        db.refresh(vital)
        vital = _vital_query(db).filter(PatientVitals.id == vital.id).first()

        process_vital_alerts(
            db=db,
            vital=vital,
            nurse_id=nurse_id,
            mark_critical=bool(vital_data.mark_critical),
        )

        bed = nh.occupied_bed_for_patient(db, vital.patient_id)
        return _serialize_vital(
            vital,
            bed_number=bed.bed_number if bed else None,
        )
    except Exception:
        db.rollback()
        raise


def update_vital_service(
    db: Session,
    vital_id: int,
    vital_data: VitalUpdate,
    nurse_id: int,
):
    vital = db.query(PatientVitals).filter(PatientVitals.id == vital_id).first()
    if not vital:
        raise HTTPException(status_code=404, detail="Vital record not found")
    if vital.recorded_by != nurse_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update vitals you recorded",
        )

    try:
        update_data = vital_data.model_dump(exclude_unset=True)
        mark_critical = bool(update_data.pop("mark_critical", False))

        if "status" in update_data and update_data["status"] is not None:
            status_value = update_data["status"]
            try:
                update_data["status"] = VitalStatus(status_value)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid vital status. Use: recorded, reviewed",
                ) from exc

        for field, value in update_data.items():
            setattr(vital, field, value)

        vital.updated_by = nurse_id
        vital.updated_at = nh.now_ist()

        db.commit()
        db.refresh(vital)
        vital = _vital_query(db).filter(PatientVitals.id == vital.id).first()

        process_vital_alerts(
            db=db,
            vital=vital,
            nurse_id=nurse_id,
            mark_critical=mark_critical,
        )

        bed = nh.occupied_bed_for_patient(db, vital.patient_id)
        return _serialize_vital(
            vital,
            bed_number=bed.bed_number if bed else None,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def get_vital_by_id_service(db: Session, vital_id: int):
    vital = _vital_query(db).filter(PatientVitals.id == vital_id).first()
    if not vital:
        raise HTTPException(status_code=404, detail="Vital record not found")
    bed = nh.occupied_bed_for_patient(db, vital.patient_id)
    return _serialize_vital(vital, bed_number=bed.bed_number if bed else None)


def get_all_vitals_service(db: Session, page: int = 1, page_size: int = 20):
    vitals = (
        _vital_query(db)
        .order_by(PatientVitals.recorded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _serialize_vitals(db, vitals)


def search_vitals_service(
    db: Session,
    patient_id: int | None = None,
    patient_uid: str | None = None,
    appointment_id: int | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    recorded_by: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = _vital_query(db).join(Patient, Patient.id == PatientVitals.patient_id)

    if patient_id:
        query = query.filter(PatientVitals.patient_id == patient_id)
    if appointment_id:
        query = query.filter(PatientVitals.appointment_id == appointment_id)
    if name:
        query = query.filter(
            or_(
                Patient.first_name.ilike(f"%{name}%"),
                Patient.last_name.ilike(f"%{name}%"),
            )
        )
    if phone:
        query = query.filter(Patient.phone.ilike(f"%{phone}%"))
    if patient_uid:
        query = query.filter(Patient.patient_uid.ilike(f"%{patient_uid}%"))
    if status:
        query = query.filter(PatientVitals.status == status)
    if recorded_by:
        query = query.filter(PatientVitals.recorded_by == recorded_by)
    if from_date:
        query = query.filter(PatientVitals.recorded_at >= from_date)
    if to_date:
        query = query.filter(
            PatientVitals.recorded_at < (to_date + timedelta(days=1))
        )

    vitals = (
        query.order_by(PatientVitals.recorded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _serialize_vitals(db, vitals)
