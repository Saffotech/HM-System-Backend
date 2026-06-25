from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class VisitsByDepartmentItem(BaseModel):
    department_id: int
    department_name: str
    visit_count: int


class RevenueByPaymentModeItem(BaseModel):
    payment_mode: str
    total_amount: float
    transaction_count: int


class AdminReportsOverviewResponse(BaseModel):
    from_date: date
    to_date: date
    total_patients: int
    new_patients_in_period: int
    total_visits: int
    completed_visits: int
    pending_payments: int
    total_revenue: float
    collected_revenue: float
    outstanding_revenue: float
    visits_by_department: List[VisitsByDepartmentItem]
    revenue_by_payment_mode: List[RevenueByPaymentModeItem]


class AdminVisitsReportItem(BaseModel):
    visit_id: int
    bill_number: str
    token_number: str
    patient_id: int
    department_id: int
    department_name: str
    doctor_id: Optional[int] = None
    grand_total: float
    paid_amount: Optional[float] = None
    payment_status: str
    status: str
    visit_date: Optional[str] = None


class AdminVisitsReportResponse(BaseModel):
    from_date: date
    to_date: date
    total: int
    visits: List[AdminVisitsReportItem]
