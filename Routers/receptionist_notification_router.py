"""Receptionist notification APIs."""

from fastapi import APIRouter

from Routers.doctor_notification_router import register_notification_routes

router = APIRouter(prefix="/receptionist/notifications", tags=["Receptionist Notifications"])

register_notification_routes(router)
