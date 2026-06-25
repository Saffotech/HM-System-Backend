from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from Models.department import Department
from Models.opd_billing import PaymentTransaction
from Models.patient import OpdVisit, Patient
from Schemas.admin_reports_schema import (
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
) -> tuple[date, date, datetime, datetime]:
    today = datetime.now(IST).date()
    start_day = from_date or today.replace(day=1)
    end_day = to_date or today
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    period_start, _ = _day_bounds(start_day)
    _, period_end = _day_bounds(end_day)
    return start_day, end_day, period_start, period_end


def get_reports_overview(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> AdminReportsOverviewResponse:
    start_day, end_day, period_start, period_end = _period_bounds(from_date, to_date)

    total_patients = int(db.query(func.count(Patient.id)).scalar() or 0)
    new_patients_in_period = int(
        db.query(func.count(Patient.id))
        .filter(Patient.created_at >= period_start, Patient.created_at <= period_end)
        .scalar()
        or 0
    )

    visit_base = db.query(OpdVisit).filter(
        OpdVisit.visit_date >= period_start,
        OpdVisit.visit_date <= period_end,
    )
    total_visits = int(visit_base.count())
    completed_visits = int(
        visit_base.filter(OpdVisit.status.in_(["completed", "discharged"])).count()
    )
    pending_payments = int(
        visit_base.filter(OpdVisit.payment_status != "paid").count()
    )

    revenue_row = (
        db.query(
            func.coalesce(func.sum(OpdVisit.grand_total), 0.0),
            func.coalesce(func.sum(OpdVisit.paid_amount), 0.0),
        )
        .filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
        .one()
    )
    total_revenue = float(revenue_row[0] or 0)
    collected_revenue = float(revenue_row[1] or 0)
    outstanding_revenue = round(total_revenue - collected_revenue, 2)

    dept_rows = (
        db.query(
            Department.id,
            Department.name,
            func.count(OpdVisit.id),
        )
        .outerjoin(
            OpdVisit,
            (OpdVisit.department_id == Department.id)
            & (OpdVisit.visit_date >= period_start)
            & (OpdVisit.visit_date <= period_end),
        )
        .group_by(Department.id, Department.name)
        .order_by(func.count(OpdVisit.id).desc())
        .all()
    )

    payment_rows = (
        db.query(
            PaymentTransaction.payment_mode,
            func.coalesce(func.sum(PaymentTransaction.amount), 0.0),
            func.count(PaymentTransaction.id),
        )
        .join(OpdVisit, OpdVisit.id == PaymentTransaction.visit_id)
        .filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
        .group_by(PaymentTransaction.payment_mode)
        .order_by(func.sum(PaymentTransaction.amount).desc())
        .all()
    )

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


def get_visits_report(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    department_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
) -> AdminVisitsReportResponse:
    start_day, end_day, period_start, period_end = _period_bounds(from_date, to_date)

    query = (
        db.query(OpdVisit, Department.name)
        .join(Department, Department.id == OpdVisit.department_id)
        .filter(
            OpdVisit.visit_date >= period_start,
            OpdVisit.visit_date <= period_end,
        )
    )
    if department_id is not None:
        query = query.filter(OpdVisit.department_id == department_id)

    total = int(query.count())
    rows = (
        query.order_by(OpdVisit.visit_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    visits = [
        AdminVisitsReportItem(
            visit_id=visit.id,
            bill_number=visit.bill_number,
            token_number=visit.token_number,
            patient_id=visit.patient_id,
            department_id=visit.department_id,
            department_name=dept_name,
            doctor_id=visit.doctor_id,
            grand_total=float(visit.grand_total or 0),
            paid_amount=float(visit.paid_amount) if visit.paid_amount is not None else None,
            payment_status=visit.payment_status,
            status=visit.status,
            visit_date=visit.visit_date.isoformat() if visit.visit_date else None,
        )
        for visit, dept_name in rows
    ]

    return AdminVisitsReportResponse(
        from_date=start_day,
        to_date=end_day,
        total=total,
        visits=visits,
    )
