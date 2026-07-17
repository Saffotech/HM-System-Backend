from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ReceptionistAppointmentStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


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
    doctor_name: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None
    status: ReceptionistAppointmentStatus
    payment_status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    checked_in_at: Optional[datetime] = None
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


class DoctorScheduleSlot(BaseModel):
    slot_start: str
    slot_end: str
    is_available: bool
    status: str


class DoctorScheduleItem(BaseModel):
    doctor_id: int
    doctor_name: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    specialization: Optional[str] = None
    shift_name: Optional[str] = None
    shift_start_time: Optional[str] = None
    shift_end_time: Optional[str] = None
    appointments_count: int = 0
    scheduled_count: int = 0
    completed_count: int = 0
    cancelled_count: int = 0
    is_available: bool = True
    slots: Optional[list[DoctorScheduleSlot]] = None
    total_slots: int = 0
    booked_slots: int = 0
    available_slots: int = 0


class DoctorsScheduleResponse(BaseModel):
    success: bool = True
    date: date
    total: int
    page: int
    page_size: int
    doctors: list[DoctorScheduleItem]
