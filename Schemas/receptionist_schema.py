from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ReceptionistAppointmentStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"


class ReceptionistDashboardData(BaseModel):
    total_patients: int
    completed: int
    todays_paid_appointments: int
    todays_unpaid_appointments: int
    todays_cancelled: int


class DashboardResponse(BaseModel):
    success: bool = True
    data: ReceptionistDashboardData


class QueueItemOut(BaseModel):
    appointment_id: int
    appointment_uid: Optional[str] = None
    patient_id: int
    patient_name: str
    patient_uid: str
    patient_phone: Optional[str] = None
    doctor_id: int
    status: ReceptionistAppointmentStatus
    payment_status: Optional[str] = None
    checked_in_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    consultation_started_at: Optional[datetime] = None
    consultation_completed_at: Optional[datetime] = None
    queue_date: Optional[date] = None


class DoctorQueueResponse(BaseModel):
    success: bool = True
    doctor_id: int
    total: int
    page: int
    limit: int
    queue: list[QueueItemOut]


class QueueHistoryItem(QueueItemOut):
    doctor_name: Optional[str] = None


class QueueHistoryResponse(BaseModel):
    success: bool = True
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total: int
    page: int
    limit: int
    history: list[QueueHistoryItem]


class TodayQueueItem(QueueItemOut):
    doctor_name: Optional[str] = None


class TodayQueueResponse(BaseModel):
    success: bool = True
    queue_date: date
    total: int
    page: int
    limit: int
    queue: list[TodayQueueItem]


class DoctorScheduleItem(BaseModel):
    doctor_id: int
    doctor_name: str
    department: Optional[str] = None
    specialization: Optional[str] = None
    schedule_date: date
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    total_slots: int = 0
    booked_slots: int = 0
    available_slots: int = 0
    status: str


class DoctorScheduleListResponse(BaseModel):
    success: bool = True
    total_records: int
    total_pages: int
    current_page: int
    page_size: int
    items: list[DoctorScheduleItem]
