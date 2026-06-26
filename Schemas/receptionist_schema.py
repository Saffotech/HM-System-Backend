from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from Models.doctor_patient_queue import QueueStatus
from Models.doctor_queue_next_request import NextRequestStatus


class ReceptionistDashboardData(BaseModel):
    total_patients: int
    waiting: int
    called: int
    in_progress: int
    completed: int
    no_show: int
    pending_doctor_requests: int
    todays_arrivals: int
    todays_checked_in: int
    todays_cancelled: int
    average_waiting_time_minutes: Optional[float] = None


class DashboardResponse(BaseModel):
    success: bool = True
    data: ReceptionistDashboardData


class ArrivalItem(BaseModel):
    appointment_id: int
    appointment_uid: str
    patient_id: int
    patient_name: str
    patient_uid: str
    patient_phone: Optional[str] = None
    doctor_id: int
    doctor_name: str
    scheduled_at: str


class ArrivalsResponse(BaseModel):
    success: bool = True
    total: int
    page: int
    limit: int
    arrivals: list[ArrivalItem]


class QueueItemOut(BaseModel):
    queue_id: int
    appointment_id: int
    appointment_uid: Optional[str] = None
    queue_number: int
    patient_id: int
    patient_name: str
    patient_uid: str
    patient_phone: Optional[str] = None
    doctor_id: int
    status: QueueStatus
    checked_in_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    called_by: Optional[int] = None
    called_by_name: Optional[str] = None
    consultation_started_at: Optional[datetime] = None
    consultation_completed_at: Optional[datetime] = None
    queue_date: Optional[date] = None


class CheckInResponse(BaseModel):
    success: bool = True
    message: str
    queue: QueueItemOut


class DoctorQueueResponse(BaseModel):
    success: bool = True
    doctor_id: int
    total: int
    page: int
    limit: int
    queue: list[QueueItemOut]


class PendingCallItem(BaseModel):
    request_id: int
    doctor_id: int
    doctor_name: Optional[str] = None
    queue_id: Optional[int] = None
    queue_number: Optional[int] = None
    appointment_id: int
    patient_id: int
    patient_name: Optional[str] = None
    patient_uid: Optional[str] = None
    appointment_time: Optional[str] = None
    status: NextRequestStatus
    requested_at: datetime


class PendingCallsResponse(BaseModel):
    success: bool = True
    total: int
    pending_calls: list[PendingCallItem]


class CallPatientResponse(BaseModel):
    success: bool = True
    message: str
    queue: QueueItemOut


class QueueActionResponse(BaseModel):
    success: bool = True
    message: str
    queue: QueueItemOut


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
