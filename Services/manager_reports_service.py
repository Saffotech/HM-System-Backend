from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from Models.department import Department
from Models.ipd import IpdAdmission, IpdBill, IpdPaymentTransaction
from Models.opd_billing import Appointment, AppointmentStatus, PaymentTransaction
from Models.patient import OpdVisit, Patient
from Models.user import User
from Services.opd_helpers import display_name
from Schemas.manager_reports_schema import (
    AdminReportsOverviewResponse,
    AdminVisitsReportItem,
    AdminVisitsReportResponse,
    RevenueByPaymentModeItem,
    VisitsByDepartmentItem,
)

IST = ZoneInfo("Asia/Kolkata")


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=IST)
    end = datetime.combine(d, time.max, tzinfo=IST)
    return start, end


def _period_bounds(
    from_date: Optional[date],
    to_date: Optional[date],
) -> tuple[date, date, datetime, datetime, bool]:
    """Return the inclusive hospital-day window.

    Both dates omitted means no date limit. A missing date used to fall back
    to the current month, which hid every visit that was not created this month.
    """
    today = datetime.now(IST).date()
    bounded = from_date is not None or to_date is not None
    if not bounded:
        start_day = date(2000, 1, 1)
        end_day = today
    else:
        start_day = from_date or date(2000, 1, 1)
        end_day = to_date or today
        if start_day > end_day:
            start_day, end_day = end_day, start_day
    period_start, _ = _day_bounds(start_day)
    _, period_end = _day_bounds(end_day)
    return start_day, end_day, period_start, period_end, bounded


def get_reports_overview(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> AdminReportsOverviewResponse:
    start_day, end_day, period_start, period_end, bounded = _period_bounds(from_date, to_date)

    total_patients = int(db.query(func.count(Patient.id)).scalar() or 0)
    if bounded:
        registered_ids = {
            patient_id
            for (patient_id,) in db.query(Patient.id)
            .filter(
                Patient.created_at >= period_start,
                Patient.created_at <= period_end,
            )
            .all()
        }
        admitted_ids = {
            patient_id
            for (patient_id,) in db.query(IpdAdmission.patient_id)
            .filter(
                IpdAdmission.status != "cancelled",
                IpdAdmission.admitted_at >= period_start,
                IpdAdmission.admitted_at <= period_end,
            )
            .distinct()
            .all()
        }
        new_patients_in_period = len(registered_ids | admitted_ids)
    else:
        new_patients_in_period = total_patients

    visit_base = db.query(OpdVisit)
    if bounded:
        visit_base = visit_base.filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
    total_visits = int(visit_base.count())
    # Completing a consultation marks the appointment completed and leaves
    # opd_visits.status as registered. Count either stored visit status.
    completed_appointment_ids = db.query(Appointment.id).filter(
        Appointment.status == AppointmentStatus.completed
    )
    completed_visits = int(
        visit_base.filter(
            OpdVisit.status != "cancelled",
            or_(
                OpdVisit.status.in_(["completed", "discharged"]),
                OpdVisit.appointment_id.in_(completed_appointment_ids),
            ),
        ).count()
    )
    pending_query = db.query(
        func.coalesce(func.sum(OpdVisit.balance_due), 0.0)
    ).filter(
        OpdVisit.status != "cancelled",
        OpdVisit.payment_status.in_(["pending", "partial"]),
    )
    if bounded:
        pending_query = pending_query.filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
    pending_payments = round(float(pending_query.scalar() or 0), 2)

    revenue_query = db.query(
        func.coalesce(func.sum(OpdVisit.grand_total), 0.0),
        func.coalesce(func.sum(OpdVisit.paid_amount), 0.0),
    )
    if bounded:
        revenue_query = revenue_query.filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
    revenue_row = revenue_query.one()
    total_revenue = float(revenue_row[0] or 0)
    collected_revenue = float(revenue_row[1] or 0)

    ipd_bill_query = db.query(
        func.coalesce(func.sum(IpdBill.grand_total), 0.0),
        func.coalesce(func.sum(IpdBill.paid_amount), 0.0),
    ).filter(IpdBill.status != "void")
    ipd_pending_query = db.query(
        func.coalesce(func.sum(IpdBill.balance_due), 0.0)
    ).filter(
        IpdBill.status != "void",
        IpdBill.payment_status.in_(["pending", "partial"]),
    )
    if bounded:
        ipd_bill_query = ipd_bill_query.filter(
            IpdBill.generated_at >= period_start,
            IpdBill.generated_at <= period_end,
        )
        ipd_pending_query = ipd_pending_query.filter(
            IpdBill.generated_at >= period_start,
            IpdBill.generated_at <= period_end,
        )
    ipd_revenue, ipd_collected = ipd_bill_query.one()
    total_revenue += float(ipd_revenue or 0)
    collected_revenue += float(ipd_collected or 0)
    pending_payments = round(
        pending_payments + float(ipd_pending_query.scalar() or 0),
        2,
    )
    outstanding_revenue = round(total_revenue - collected_revenue, 2)

    dept_rows = (
        db.query(
            Department.id,
            Department.name,
            func.count(OpdVisit.id),
        )
        .outerjoin(
            OpdVisit,
            and_(
                OpdVisit.department_id == Department.id,
                *([
                    OpdVisit.visit_date >= period_start,
                    OpdVisit.visit_date <= period_end,
                ] if bounded else []),
            ),
        )
        .group_by(Department.id, Department.name)
        .order_by(func.count(OpdVisit.id).desc())
        .all()
    )

    payment_query = (
        db.query(
            PaymentTransaction.payment_mode,
            func.coalesce(func.sum(PaymentTransaction.amount), 0.0),
            func.count(PaymentTransaction.id),
        )
        .join(OpdVisit, OpdVisit.id == PaymentTransaction.visit_id)
    )
    if bounded:
        payment_query = payment_query.filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
    payment_rows = (
        payment_query
        .group_by(PaymentTransaction.payment_mode)
        .all()
    )
    ipd_payment_query = (
        db.query(
            IpdPaymentTransaction.payment_mode,
            func.coalesce(func.sum(IpdPaymentTransaction.amount), 0.0),
            func.count(IpdPaymentTransaction.id),
        )
        .join(IpdBill, IpdBill.id == IpdPaymentTransaction.bill_id)
        .filter(IpdBill.status != "void")
    )
    if bounded:
        ipd_payment_query = ipd_payment_query.filter(
            IpdBill.generated_at >= period_start,
            IpdBill.generated_at <= period_end,
        )
    ipd_payment_rows = (
        ipd_payment_query.group_by(IpdPaymentTransaction.payment_mode).all()
    )
    combined_payments: dict[str, tuple[float, int]] = {}
    for mode, amount, count in list(payment_rows) + list(ipd_payment_rows):
        key = mode or "unknown"
        current_amount, current_count = combined_payments.get(key, (0.0, 0))
        combined_payments[key] = (
            current_amount + float(amount or 0),
            current_count + int(count or 0),
        )
    payment_rows = sorted(
        ((mode, amount, count) for mode, (amount, count) in combined_payments.items()),
        key=lambda row: row[1],
        reverse=True,
    )

    if not bounded:
        earliest_values = [
            db.query(func.min(OpdVisit.visit_date)).scalar(),
            db.query(func.min(IpdBill.generated_at))
            .filter(IpdBill.status != "void")
            .scalar(),
            db.query(func.min(IpdAdmission.admitted_at))
            .filter(IpdAdmission.status != "cancelled")
            .scalar(),
        ]
        earliest_dates = []
        for earliest in earliest_values:
            if earliest is None:
                continue
            if earliest.tzinfo is None:
                earliest = earliest.replace(tzinfo=IST)
            earliest_dates.append(earliest.astimezone(IST).date())
        if earliest_dates:
            start_day = min(earliest_dates)

    return AdminReportsOverviewResponse(
        from_date=start_day,
        to_date=end_day,
        total_patients=total_patients,
        new_patients_in_period=new_patients_in_period,
        total_visits=total_visits,
        completed_visits=completed_visits,
        pending_payments=pending_payments,
        total_revenue=round(total_revenue, 2),
        collected_revenue=round(collected_revenue, 2),
        outstanding_revenue=outstanding_revenue,
        visits_by_department=[
            VisitsByDepartmentItem(
                department_id=dept_id,
                department_name=name,
                visit_count=int(count or 0),
            )
            for dept_id, name, count in dept_rows
        ],
        revenue_by_payment_mode=[
            RevenueByPaymentModeItem(
                payment_mode=mode or "unknown",
                total_amount=round(float(amount or 0), 2),
                transaction_count=int(count or 0),
            )
            for mode, amount, count in payment_rows
        ],
    )


IPD_REPORT_ID_OFFSET = 1_000_000_000


def _iso_ist(value) -> Optional[str]:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(IST).isoformat()


def _patient_fields(patient: Optional[Patient]) -> tuple[Optional[str], Optional[str]]:
    if patient is None:
        return None, None
    return patient.patient_uid, display_name(patient.first_name, patient.last_name)


def _doctor_names(db: Session, doctor_ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    if not doctor_ids:
        return names
    for doctor in db.query(User).filter(User.id.in_(doctor_ids)).all():
        name = display_name(doctor.first_name, doctor.last_name, prefix="Dr. ")
        if name and name != "Dr.":
            names[doctor.id] = name
    return names


def _report_source(source: Optional[str]) -> str:
    key = (source or "all").strip().lower()
    if key not in {"opd", "ipd", "all"}:
        return "all"
    return key


def _opd_visit_status(visit: OpdVisit, completed_appointment_ids: set[int]) -> str:
    raw = (visit.status or "").strip().lower()
    if raw in {"complete", "completed"}:
        return "complete"
    if raw in {"admit", "admitted"}:
        return "admit"
    if raw == "discharged":
        return "discharged"
    if raw == "cancelled":
        return "cancelled"
    if visit.appointment_id and visit.appointment_id in completed_appointment_ids:
        return "complete"
    return raw


def _ipd_visit_status(status: Optional[str]) -> str:
    raw = (status or "").strip().lower()
    if raw in {"admit", "admitted"}:
        return "admit"
    if raw == "discharged":
        return "discharged"
    return raw


def _latest_ipd_bills(db: Session, admission_ids: list[int]) -> dict[int, IpdBill]:
    latest: dict[int, IpdBill] = {}
    if not admission_ids:
        return latest
    rows = (
        db.query(IpdBill)
        .filter(
            IpdBill.admission_id.in_(admission_ids),
            IpdBill.status != "void",
        )
        .order_by(IpdBill.generated_at.desc(), IpdBill.id.desc())
        .all()
    )
    for bill in rows:
        latest.setdefault(bill.admission_id, bill)
    return latest


def get_visits_report(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    department_id: Optional[int] = None,
    source: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> AdminVisitsReportResponse:
    start_day, end_day, period_start, period_end, bounded = _period_bounds(from_date, to_date)
    include = _report_source(source)
    visits: list[AdminVisitsReportItem] = []

    if include in {"opd", "all"}:
        opd_query = (
            db.query(OpdVisit, Department.name, Patient)
            .outerjoin(Department, Department.id == OpdVisit.department_id)
            .outerjoin(Patient, Patient.id == OpdVisit.patient_id)
        )
        if bounded:
            opd_query = opd_query.filter(
                OpdVisit.visit_date >= period_start,
                OpdVisit.visit_date <= period_end,
            )
        if department_id is not None:
            opd_query = opd_query.filter(OpdVisit.department_id == department_id)
        opd_rows = opd_query.all()
        completed_appointment_ids = {
            appointment_id
            for (appointment_id,) in db.query(Appointment.id)
            .filter(Appointment.status == AppointmentStatus.completed)
            .all()
            if appointment_id
        }
        doctor_names = _doctor_names(
            db, {visit.doctor_id for visit, _dept, _patient in opd_rows if visit.doctor_id}
        )
        for visit, dept_name, patient in opd_rows:
            patient_uid, patient_name = _patient_fields(patient)
            visits.append(
                AdminVisitsReportItem(
                    visit_id=visit.id,
                    bill_number=visit.bill_number,
                    token_number=visit.token_number,
                    patient_id=visit.patient_id,
                    patient_uid=patient_uid,
                    patient_name=patient_name,
                    department_id=visit.department_id,
                    department_name=dept_name or "",
                    doctor_id=visit.doctor_id,
                    doctor_name=doctor_names.get(visit.doctor_id),
                    grand_total=float(visit.grand_total or 0),
                    paid_amount=(
                        float(visit.paid_amount) if visit.paid_amount is not None else None
                    ),
                    payment_status=visit.payment_status,
                    status=_opd_visit_status(visit, completed_appointment_ids),
                    visit_date=_iso_ist(visit.visit_date),
                    source="opd",
                )
            )

    if include in {"ipd", "all"}:
        ipd_query = (
            db.query(IpdAdmission, Department.name, Patient)
            .outerjoin(Department, Department.id == IpdAdmission.department_id)
            .outerjoin(Patient, Patient.id == IpdAdmission.patient_id)
            .filter(IpdAdmission.status != "cancelled")
        )
        if bounded:
            ipd_query = ipd_query.filter(
                IpdAdmission.admitted_at >= period_start,
                IpdAdmission.admitted_at <= period_end,
            )
        if department_id is not None:
            ipd_query = ipd_query.filter(IpdAdmission.department_id == department_id)
        ipd_rows = ipd_query.all()
        bills = _latest_ipd_bills(db, [admission.id for admission, _dept, _patient in ipd_rows])
        doctor_names = _doctor_names(
            db,
            {
                admission.doctor_id
                for admission, _dept, _patient in ipd_rows
                if admission.doctor_id
            },
        )
        for admission, dept_name, patient in ipd_rows:
            patient_uid, patient_name = _patient_fields(patient)
            bill = bills.get(admission.id)
            visits.append(
                AdminVisitsReportItem(
                    visit_id=IPD_REPORT_ID_OFFSET + admission.id,
                    bill_number=(bill.bill_number if bill else admission.admission_no),
                    token_number=admission.admission_no,
                    patient_id=admission.patient_id,
                    patient_uid=patient_uid,
                    patient_name=patient_name,
                    department_id=admission.department_id or 0,
                    department_name=dept_name or admission.ward_name or "",
                    doctor_id=admission.doctor_id,
                    doctor_name=doctor_names.get(admission.doctor_id),
                    grand_total=float(bill.grand_total or 0) if bill else 0.0,
                    paid_amount=(
                        float(bill.paid_amount) if bill and bill.paid_amount is not None else None
                    ),
                    payment_status=bill.payment_status if bill else "pending",
                    status=_ipd_visit_status(admission.status),
                    visit_date=_iso_ist(admission.admitted_at),
                    source="ipd",
                )
            )

    visits.sort(key=lambda row: row.visit_date or "", reverse=True)
    total = len(visits)
    start = max(0, (page - 1) * limit)
    visits = visits[start : start + limit]

    if not bounded:
        earliest_values = [
            db.query(func.min(OpdVisit.visit_date)).scalar(),
            db.query(func.min(IpdAdmission.admitted_at))
            .filter(IpdAdmission.status != "cancelled")
            .scalar(),
        ]
        earliest_dates = []
        for earliest in earliest_values:
            if earliest is None:
                continue
            if earliest.tzinfo is None:
                earliest = earliest.replace(tzinfo=IST)
            earliest_dates.append(earliest.astimezone(IST).date())
        if earliest_dates:
            start_day = min(earliest_dates)

    return AdminVisitsReportResponse(
        from_date=start_day,
        to_date=end_day,
        total=total,
        visits=visits,
    )
